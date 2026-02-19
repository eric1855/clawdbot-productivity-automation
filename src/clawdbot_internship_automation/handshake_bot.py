from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import (
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from .models import ApplicationResult, JobPosting
from .question_answerer import QuestionAnswerer
from .resume_builder import ResumeBuilder
from .settings import AutomationConfig

LOGGER = logging.getLogger(__name__)


class HandshakeBot:
    def __init__(
        self,
        config: AutomationConfig,
        resume_builder: ResumeBuilder,
        question_answerer: QuestionAnswerer,
        base_resume_text: str,
    ):
        self.config = config
        self.resume_builder = resume_builder
        self.question_answerer = question_answerer
        self.base_resume_text = base_resume_text

    def run(self) -> list[ApplicationResult]:
        results: list[ApplicationResult] = []
        applied_or_ready = 0

        with sync_playwright() as playwright:
            browser, context = self._new_browser(playwright)
            try:
                page = context.new_page()
                page.set_default_timeout(self.config.browser.timeout_ms)
                self._login(page)

                jobs = self._discover_jobs(page)
                LOGGER.info("Discovered %s candidate postings.", len(jobs))

                for seed_job in jobs:
                    if applied_or_ready >= self.config.application.max_applications:
                        LOGGER.info("Reached max_applications=%s", applied_or_ready)
                        break

                    job = self._enrich_job(seed_job, context)
                    if not self._matches_filters(job):
                        results.append(
                            ApplicationResult(
                                job_id=job.job_id,
                                title=job.title,
                                company=job.company,
                                url=job.url,
                                status="skipped",
                                reason="filter_mismatch",
                            )
                        )
                        continue

                    result = self._apply_to_job(job, context)
                    results.append(result)

                    if result.status in {"applied", "ready_to_submit", "dry_run_ready"}:
                        applied_or_ready += 1
                        time.sleep(self.config.application.pause_between_apps_sec)
            finally:
                browser.close()

        self._write_results(results)
        return results

    def _new_browser(self, playwright: Playwright):
        browser = playwright.chromium.launch(
            headless=self.config.browser.headless,
            slow_mo=self.config.browser.slow_mo_ms,
        )
        context = browser.new_context()
        return browser, context

    def _login(self, page: Page) -> None:
        LOGGER.info("Opening login page.")
        self._safe_goto(page, self.config.handshake.login_url)
        self._attempt_login_submission(page, attempts=3)
        self._wait_for_login_completion(page, timeout_sec=180)
        self._safe_goto(page, self.config.handshake.jobs_url)
        self._safe_wait(page, 1500)

    def _attempt_login_submission(self, page: Page, attempts: int = 1) -> None:
        email_selectors = [
            "input[type='email']",
            "input[name='email']",
            "input[name='username']",
            "input#email",
        ]
        password_selectors = [
            "input[type='password']",
            "input[name='password']",
            "input#password",
        ]
        button_patterns = [
            re.compile(r"sign in", re.IGNORECASE),
            re.compile(r"log in", re.IGNORECASE),
            re.compile(r"continue", re.IGNORECASE),
            re.compile(r"next", re.IGNORECASE),
        ]

        for _ in range(max(1, attempts)):
            if page.is_closed():
                raise RuntimeError("Browser page was closed during login.")
            current_url = self._safe_page_url(page)
            if self._is_authenticated_url(current_url):
                return
            if "app.joinhandshake.com" not in current_url.lower():
                return

            self._fill_first(page, email_selectors, self.config.handshake.email)
            self._fill_first(page, password_selectors, self.config.handshake.password)

            clicked = self._click_button(page, button_patterns)
            if not clicked:
                clicked = self._click_submit_if_enabled(page)
            if not clicked:
                self._press_enter_first(page, password_selectors + email_selectors)

            self._safe_wait(page, 900)

    def _wait_for_login_completion(self, page: Page, timeout_sec: int) -> None:
        LOGGER.info(
            "Complete any SSO/2FA/CAPTCHA in the browser window. "
            "Waiting up to %s seconds.",
            timeout_sec,
        )
        for second in range(timeout_sec):
            if page.is_closed():
                raise RuntimeError(
                    "Browser page was closed during login. Keep the window open through SSO/2FA."
                )

            url = self._safe_page_url(page)
            if self._is_authenticated_url(url):
                LOGGER.info("Login completed.")
                return

            if second in {10, 30, 60, 120}:
                LOGGER.info("Still waiting on login completion at URL: %s", url or "unknown")

            if second % 5 == 0:
                self._attempt_login_submission(page, attempts=1)

            self._safe_wait(page, 1000)

        raise RuntimeError(
            "Timed out waiting for Handshake login completion. "
            "Finish SSO/2FA in the opened browser and re-run."
        )

    def _discover_jobs(self, page: Page) -> list[JobPosting]:
        LOGGER.info("Discovering jobs from %s", page.url)
        query = self.config.filters.search_query.strip()
        if query:
            for selector in [
                "input[placeholder*='Search']",
                "input[type='search']",
                "input[name='query']",
            ]:
                box = page.locator(selector)
                if box.count() > 0:
                    try:
                        box.first.fill(query)
                        box.first.press("Enter")
                        page.wait_for_timeout(1200)
                        break
                    except Exception:
                        continue

        for _ in range(5):
            page.mouse.wheel(0, 3500)
            page.wait_for_timeout(600)

        anchors = page.locator("a[href*='/jobs/'], a[href*='/postings/']")
        count = min(anchors.count(), self.config.filters.max_discovered_jobs * 4)
        seen_urls: set[str] = set()
        jobs: list[JobPosting] = []

        for idx in range(count):
            node = anchors.nth(idx)
            href = (node.get_attribute("href") or "").strip()
            if not href:
                continue
            if "/jobs/" not in href and "/postings/" not in href:
                continue

            url = urljoin(page.url, href.split("?")[0])
            if url in seen_urls:
                continue
            seen_urls.add(url)

            title = (node.inner_text() or "").splitlines()[0].strip()
            job_id = self._extract_job_id(url, idx)
            jobs.append(JobPosting(job_id=job_id, title=title or "Unknown Role", url=url))

            if len(jobs) >= self.config.filters.max_discovered_jobs:
                break

        return jobs

    def _enrich_job(self, seed: JobPosting, context: BrowserContext) -> JobPosting:
        page = context.new_page()
        page.set_default_timeout(self.config.browser.timeout_ms)
        try:
            page.goto(seed.url, wait_until="domcontentloaded")
            page.wait_for_timeout(900)

            title = self._first_text(page, ["h1"]) or seed.title
            company = self._first_text(
                page,
                [
                    "a[href*='/employers/']",
                    "[data-testid='employer-name']",
                    "[data-qa='employer-name']",
                ],
            )
            location = self._first_text(
                page,
                [
                    "[data-testid='location']",
                    "[data-qa='job-location']",
                    "main span",
                ],
            )
            description = self._first_text(page, ["main", "article", "body"])[:12000]

            return JobPosting(
                job_id=seed.job_id,
                title=title or seed.title,
                company=company,
                location=location,
                description=description,
                url=seed.url,
            )
        except Exception as exc:
            LOGGER.warning("Could not enrich job %s: %s", seed.url, exc)
            return seed
        finally:
            page.close()

    def _matches_filters(self, job: JobPosting) -> bool:
        text = f"{job.title}\n{job.company}\n{job.location}\n{job.description}".lower()

        include = [kw.lower() for kw in self.config.filters.include_keywords if kw.strip()]
        exclude = [kw.lower() for kw in self.config.filters.exclude_keywords if kw.strip()]
        preferred_locations = [
            kw.lower() for kw in self.config.filters.preferred_locations if kw.strip()
        ]

        if include and not any(kw in text for kw in include):
            return False
        if exclude and any(kw in text for kw in exclude):
            return False
        if self.config.filters.remote_only and "remote" not in text:
            return False
        if preferred_locations and not any(loc in text for loc in preferred_locations):
            return False
        return True

    def _apply_to_job(self, job: JobPosting, context: BrowserContext) -> ApplicationResult:
        LOGGER.info("Applying to: %s (%s)", job.title, job.url)
        page = context.new_page()
        page.set_default_timeout(self.config.browser.timeout_ms)
        uploaded_resume = False

        try:
            page.goto(job.url, wait_until="domcontentloaded")
            page.wait_for_timeout(1000)

            if not self._click_apply(page):
                return ApplicationResult(
                    job_id=job.job_id,
                    title=job.title,
                    company=job.company,
                    url=job.url,
                    status="skipped",
                    reason="apply_button_not_found",
                )

            resume_path = self.resume_builder.build(
                job=job,
                defaults=self.question_answerer.defaults,
                base_resume_text=self.base_resume_text,
            )

            for _ in range(14):
                if not uploaded_resume:
                    uploaded_resume = self._upload_resume_if_visible(page, resume_path)

                self._fill_visible_fields(page, job)

                if self._has_submit_button(page):
                    if self.config.application.dry_run or not self.config.application.auto_submit:
                        return ApplicationResult(
                            job_id=job.job_id,
                            title=job.title,
                            company=job.company,
                            url=job.url,
                            status="dry_run_ready",
                            reason="submit_button_reached",
                        )
                    self._click_submit(page)
                    return ApplicationResult(
                        job_id=job.job_id,
                        title=job.title,
                        company=job.company,
                        url=job.url,
                        status="applied",
                    )

                if not self._click_next_step(page):
                    break

                page.wait_for_timeout(1000)

            return ApplicationResult(
                job_id=job.job_id,
                title=job.title,
                company=job.company,
                url=job.url,
                status="failed",
                reason="unable_to_reach_submit",
            )
        except Exception as exc:
            self._save_failure_html(page, job.job_id)
            return ApplicationResult(
                job_id=job.job_id,
                title=job.title,
                company=job.company,
                url=job.url,
                status="failed",
                reason=str(exc),
            )
        finally:
            page.close()

    def _save_failure_html(self, page: Page, job_id: str) -> None:
        if not self.config.application.save_html_on_failure:
            return
        try:
            failure_dir = Path("artifacts/failures")
            failure_dir.mkdir(parents=True, exist_ok=True)
            html = page.content()
            failure_path = failure_dir / f"{job_id}.html"
            failure_path.write_text(html)
        except Exception:
            return

    def _fill_visible_fields(self, page: Page, job: JobPosting) -> None:
        self._fill_text_inputs(page, job)
        self._fill_select_inputs(page, job)
        self._fill_radio_inputs(page, job)
        self._fill_checkboxes(page)

    def _fill_text_inputs(self, page: Page, job: JobPosting) -> None:
        fields = page.locator(
            "input:not([type='hidden']):not([type='file']):not([type='radio']):not([type='checkbox']), textarea"
        )
        count = min(fields.count(), 300)
        for i in range(count):
            field = fields.nth(i)
            if not self._is_visible(field):
                continue
            if self._is_disabled(field):
                continue
            value = self._input_value(field)
            if value.strip():
                continue

            input_type = (field.get_attribute("type") or "text").strip().lower()
            prompt = self._prompt_for_input(page, field)
            answer = self.question_answerer.answer(
                prompt=prompt,
                input_type=input_type,
                job=job,
                choices=[],
            )
            if not answer:
                continue
            try:
                field.fill(answer)
            except Exception:
                continue

    def _fill_select_inputs(self, page: Page, job: JobPosting) -> None:
        selects = page.locator("select")
        count = min(selects.count(), 100)
        for i in range(count):
            field = selects.nth(i)
            if not self._is_visible(field):
                continue
            if self._is_disabled(field):
                continue

            prompt = self._prompt_for_input(page, field)
            options = self._select_options(field)
            if not options:
                continue
            labels = [item["label"] for item in options]

            answer = self.question_answerer.answer(
                prompt=prompt,
                input_type="select",
                job=job,
                choices=labels,
            )
            selected = ""
            if answer:
                selected = self._best_choice(answer, labels)

            if not selected:
                selected = labels[0]

            value = ""
            for opt in options:
                if opt["label"] == selected:
                    value = opt["value"]
                    break

            try:
                if value:
                    field.select_option(value=value)
                else:
                    field.select_option(label=selected)
            except Exception:
                continue

    def _fill_radio_inputs(self, page: Page, job: JobPosting) -> None:
        radios = page.locator("input[type='radio']")
        count = min(radios.count(), 300)
        names: set[str] = set()
        for i in range(count):
            name = (radios.nth(i).get_attribute("name") or "").strip()
            if name:
                names.add(name)

        for name in names:
            group = page.locator(f"input[type='radio'][name='{name}']")
            if group.count() == 0:
                continue
            if self._radio_group_has_checked(group):
                continue

            prompt = self._radio_prompt(page, group.first)
            options = self._radio_group_labels(page, group)
            if not options:
                continue
            answer = self.question_answerer.answer(
                prompt=prompt,
                input_type="radio",
                job=job,
                choices=options,
            )
            selected = self._best_choice(answer, options) if answer else options[0]
            index = options.index(selected) if selected in options else 0
            try:
                group.nth(index).check(force=True)
            except Exception:
                continue

    def _fill_checkboxes(self, page: Page) -> None:
        boxes = page.locator("input[type='checkbox']")
        count = min(boxes.count(), 200)
        for i in range(count):
            box = boxes.nth(i)
            if not self._is_visible(box):
                continue
            if self._is_disabled(box):
                continue
            try:
                if box.is_checked():
                    continue
            except Exception:
                continue

            prompt = self._prompt_for_input(page, box).lower()
            if any(
                token in prompt
                for token in (
                    "agree",
                    "consent",
                    "acknowledge",
                    "certify",
                    "privacy",
                    "terms",
                )
            ):
                try:
                    box.check(force=True)
                except Exception:
                    continue

    def _upload_resume_if_visible(self, page: Page, resume_path: Path) -> bool:
        uploaders = page.locator("input[type='file']")
        count = min(uploaders.count(), 20)
        for i in range(count):
            uploader = uploaders.nth(i)
            if not self._is_visible(uploader):
                continue
            try:
                uploader.set_input_files(str(resume_path.resolve()))
                LOGGER.info("Uploaded resume: %s", resume_path.name)
                page.wait_for_timeout(1000)
                return True
            except Exception:
                continue
        return False

    def _click_apply(self, page: Page) -> bool:
        page.wait_for_timeout(800)
        patterns = [
            re.compile(r"easy apply", re.IGNORECASE),
            re.compile(r"quick apply", re.IGNORECASE),
            re.compile(r"apply now", re.IGNORECASE),
            re.compile(r"^apply$", re.IGNORECASE),
        ]
        if self._click_button(page, patterns):
            page.wait_for_timeout(900)
            return True

        links = page.locator("a:has-text('Apply')")
        if links.count() > 0 and self._is_visible(links.first):
            try:
                links.first.click()
                page.wait_for_timeout(900)
                return True
            except Exception:
                return False
        return False

    def _has_submit_button(self, page: Page) -> bool:
        patterns = [
            re.compile(r"submit", re.IGNORECASE),
            re.compile(r"send application", re.IGNORECASE),
            re.compile(r"finish", re.IGNORECASE),
        ]
        for pattern in patterns:
            button = page.get_by_role("button", name=pattern)
            if button.count() > 0 and self._is_visible(button.first):
                return True
        return False

    def _click_submit(self, page: Page) -> None:
        patterns = [
            re.compile(r"submit", re.IGNORECASE),
            re.compile(r"send application", re.IGNORECASE),
            re.compile(r"finish", re.IGNORECASE),
        ]
        if self._click_button(page, patterns):
            page.wait_for_timeout(1500)
            return
        raise RuntimeError("Submit button not clickable")

    def _click_next_step(self, page: Page) -> bool:
        patterns = [
            re.compile(r"next", re.IGNORECASE),
            re.compile(r"continue", re.IGNORECASE),
            re.compile(r"review", re.IGNORECASE),
            re.compile(r"save and continue", re.IGNORECASE),
        ]
        return self._click_button(page, patterns)

    @staticmethod
    def _extract_job_id(url: str, index_fallback: int) -> str:
        match = re.search(r"/(?:jobs|postings)/(\d+)", url)
        if match:
            return match.group(1)
        return f"idx-{index_fallback}"

    @staticmethod
    def _first_text(page: Page, selectors: list[str]) -> str:
        for selector in selectors:
            try:
                node = page.locator(selector)
                if node.count() == 0:
                    continue
                text = (node.first.inner_text() or "").strip()
                if text:
                    return text
            except Exception:
                continue
        return ""

    @staticmethod
    def _fill_first(page: Page, selectors: list[str], value: str) -> None:
        for selector in selectors:
            node = page.locator(selector)
            if node.count() == 0:
                continue
            try:
                node.first.fill(value)
                return
            except Exception:
                continue

    @staticmethod
    def _press_enter_first(page: Page, selectors: list[str]) -> None:
        for selector in selectors:
            node = page.locator(selector)
            if node.count() == 0:
                continue
            try:
                target = node.first
                if target.is_visible():
                    target.press("Enter")
                    return
            except Exception:
                continue

    def _click_submit_if_enabled(self, page: Page) -> bool:
        buttons = page.locator("button[type='submit'], input[type='submit']")
        count = min(buttons.count(), 5)
        for i in range(count):
            button = buttons.nth(i)
            try:
                if not button.is_visible() or not button.is_enabled():
                    continue
                button.click(timeout=2000)
                return True
            except Exception:
                continue
        return False

    @staticmethod
    def _safe_page_url(page: Page) -> str:
        try:
            return page.url or ""
        except Exception:
            return ""

    @staticmethod
    def _is_authenticated_url(url: str) -> bool:
        normalized = (url or "").lower()
        if not normalized:
            return False
        if "app.joinhandshake.com/stu/" in normalized:
            return True
        return (
            "app.joinhandshake.com" in normalized
            and "/login" not in normalized
            and "/auth/" not in normalized
        )

    @staticmethod
    def _safe_wait(page: Page, milliseconds: int) -> None:
        try:
            page.wait_for_timeout(milliseconds)
        except PlaywrightError as exc:
            if "closed" in str(exc).lower():
                raise RuntimeError(
                    "Browser page was closed during login/apply flow. Keep it open while automation runs."
                ) from exc
            raise

    @staticmethod
    def _safe_goto(page: Page, url: str) -> None:
        try:
            page.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            if "closed" in str(exc).lower():
                raise RuntimeError(
                    "Browser page was closed before navigation finished."
                ) from exc
            raise

    @staticmethod
    def _click_button(page: Page, patterns: list[re.Pattern[str]]) -> bool:
        for pattern in patterns:
            try:
                button = page.get_by_role("button", name=pattern)
                if button.count() == 0:
                    continue
                target = button.first
                if target.is_visible() and target.is_enabled():
                    target.click()
                    return True
            except PlaywrightTimeoutError:
                continue
            except Exception:
                continue
        return False

    @staticmethod
    def _is_visible(locator: Locator) -> bool:
        try:
            return locator.is_visible()
        except Exception:
            return False

    @staticmethod
    def _is_disabled(locator: Locator) -> bool:
        try:
            return locator.is_disabled()
        except Exception:
            return False

    @staticmethod
    def _input_value(locator: Locator) -> str:
        try:
            return locator.input_value()
        except Exception:
            return ""

    def _prompt_for_input(self, page: Page, locator: Locator) -> str:
        input_id = (locator.get_attribute("id") or "").strip()
        if input_id:
            label = page.locator(f"label[for='{input_id}']")
            if label.count() > 0:
                text = (label.first.inner_text() or "").strip()
                if text:
                    return text

        for attr in ("aria-label", "placeholder", "name"):
            value = (locator.get_attribute(attr) or "").strip()
            if value:
                return value

        try:
            text = locator.evaluate(
                "el => (el.closest('label')?.innerText || el.closest('fieldset')?.querySelector('legend')?.innerText || '').trim()"
            )
            if text:
                return str(text)
        except Exception:
            return "Application question"
        return "Application question"

    @staticmethod
    def _select_options(select: Locator) -> list[dict[str, str]]:
        try:
            data = select.evaluate(
                """el => Array.from(el.options).map(opt => ({
                    label: (opt.textContent || '').trim(),
                    value: opt.value || ''
                })).filter(x => x.label && x.label.toLowerCase() !== 'select')
                """
            )
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _radio_prompt(self, page: Page, radio: Locator) -> str:
        try:
            legend = radio.evaluate(
                "el => (el.closest('fieldset')?.querySelector('legend')?.innerText || '').trim()"
            )
            if legend:
                return str(legend)
        except Exception:
            pass
        return self._prompt_for_input(page, radio)

    def _radio_group_labels(self, page: Page, group: Locator) -> list[str]:
        labels: list[str] = []
        count = min(group.count(), 30)
        for i in range(count):
            radio = group.nth(i)
            if not self._is_visible(radio):
                continue
            label = self._prompt_for_input(page, radio)
            value = (radio.get_attribute("value") or "").strip()
            choice = label or value or f"Option {i + 1}"
            labels.append(choice)
        return labels

    @staticmethod
    def _radio_group_has_checked(group: Locator) -> bool:
        count = min(group.count(), 30)
        for i in range(count):
            try:
                if group.nth(i).is_checked():
                    return True
            except Exception:
                continue
        return False

    @staticmethod
    def _best_choice(answer: str, options: list[str]) -> str:
        if not answer:
            return ""
        lowered = {opt.lower(): opt for opt in options}
        if answer.lower() in lowered:
            return lowered[answer.lower()]
        for option in options:
            if option.lower() in answer.lower() or answer.lower() in option.lower():
                return option
        return ""

    @staticmethod
    def _write_results(results: list[ApplicationResult]) -> None:
        out_path = Path("artifacts/application_results.jsonl")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w") as f:
            for result in results:
                f.write(
                    json.dumps(
                        {
                            "job_id": result.job_id,
                            "title": result.title,
                            "company": result.company,
                            "url": result.url,
                            "status": result.status,
                            "reason": result.reason,
                        }
                    )
                    + "\n"
                )
