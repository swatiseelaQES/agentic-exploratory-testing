from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import (
    ElementNotInteractableException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait

from .models import AgentDecision, Observation


class BrowserSession:
    def __init__(
        self,
        headless: bool,
        evidence_dir: Path,
    ):
        options = webdriver.ChromeOptions()

        if headless:
            options.add_argument("--headless=new")

        options.add_argument("--window-size=1440,1000")

        self.driver = webdriver.Chrome(
            options=options
        )

        self.wait = WebDriverWait(
            self.driver,
            5,
        )

        self.evidence_dir = evidence_dir
        self.evidence_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.step = 0

    def observe(self) -> Observation:
        self.step += 1

        screenshot = (
            self.evidence_dir
            / f"step-{self.step:03}.png"
        )

        self.driver.save_screenshot(
            str(screenshot)
        )

        elements = self.driver.execute_script(
            """
            const candidates = [
                ...document.querySelectorAll(
                    'button, a, input, select, textarea'
                )
            ];

            const visible = candidates.filter(element => {
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();

                return (
                    style.visibility !== 'hidden' &&
                    style.display !== 'none' &&
                    rect.width > 0 &&
                    rect.height > 0
                );
            });

            function labelFor(element) {
                const ariaLabel =
                    element.getAttribute('aria-label');

                if (ariaLabel) {
                    return ariaLabel.trim();
                }

                if (element.labels && element.labels.length) {
                    return [...element.labels]
                        .map(label => label.innerText.trim())
                        .join(' ');
                }

                const enclosingLabel =
                    element.closest('label');

                if (enclosingLabel) {
                    return enclosingLabel.innerText.trim();
                }

                return (
                    element.innerText ||
                    element.placeholder ||
                    element.name ||
                    element.value ||
                    ''
                ).trim();
            }

            return visible.map((element, index) => {
                const ref = `element-${index}`;

                element.setAttribute(
                    'data-agent-ref',
                    ref
                );

                return {
                    ref: ref,
                    tag: element.tagName.toLowerCase(),
                    role:
                        element.getAttribute('role') ||
                        element.type ||
                        element.tagName.toLowerCase(),
                    name: labelFor(element),
                    html_name:
                        element.getAttribute('name') || '',
                    value: element.value || '',
                    checked:
                        element.type === 'radio' ||
                        element.type === 'checkbox'
                            ? element.checked
                            : null,
                    enabled: !element.disabled
                };
            });
            """
        )

        visible_text = self.driver.find_element(
            By.TAG_NAME,
            "body",
        ).text[:6000]

        return Observation(
            url=self.driver.current_url,
            title=self.driver.title,
            visible_text=visible_text,
            elements=elements,
            screenshot=str(screenshot),
        )

    def execute(
        self,
        decision: AgentDecision,
        base_url: str,
    ) -> str | None:
        """
        Execute one bounded action.

        Returns None on success. Returns an error message when an
        action cannot be completed, allowing the agent to recover.
        """
        try:
            if decision.action == "navigate":
                url = decision.value or base_url

                if not url.startswith(base_url):
                    return (
                        "Navigation blocked because the target "
                        "is outside BASE_URL."
                    )

                self.driver.get(url)
                return None

            if decision.action == "back":
                self.driver.back()
                return None

            if decision.action == "refresh":
                self.driver.refresh()
                return None

            if decision.action in {
                "inspect",
                "finish",
            }:
                return None

            if not decision.target:
                return (
                    f"Action {decision.action} requires "
                    "a target."
                )

            element = self._find(
                ref=decision.target.ref,
                role=decision.target.role,
                name=decision.target.name,
                css=decision.target.css,
            )

            if decision.action == "click":
                element.click()

            elif decision.action == "type":
                element.send_keys(
                    decision.value or ""
                )

            elif decision.action == "clear":
                element.clear()

            elif decision.action == "select":
                Select(element).select_by_visible_text(
                    decision.value or ""
                )

            return None

        except (
            NoSuchElementException,
            StaleElementReferenceException,
            ElementNotInteractableException,
            TimeoutException,
        ) as exc:
            return (
                f"{type(exc).__name__}: "
                f"The requested element could not be used. "
                f"Choose a current element ref from the next observation."
            )

    def _find(
        self,
        ref: str | None,
        role: str | None,
        name: str | None,
        css: str | None,
    ):
        if ref:
            selector = (
                f'[data-agent-ref="{ref}"]'
            )

            return self.wait.until(
                lambda driver: driver.find_element(
                    By.CSS_SELECTOR,
                    selector,
                )
            )

        if css:
            return self.wait.until(
                lambda driver: driver.find_element(
                    By.CSS_SELECTOR,
                    css,
                )
            )

        if name:
            escaped_name = name.replace(
                "'",
                "\\'",
            )

            xpath = (
                "//*["
                "self::button or "
                "self::a or "
                "self::input or "
                "self::select or "
                "self::textarea"
                "]["
                f"@aria-label='{escaped_name}' or "
                f"@name='{escaped_name}' or "
                f"@value='{escaped_name}' or "
                f"normalize-space(.)='{escaped_name}'"
                "]"
            )

            return self.wait.until(
                lambda driver: driver.find_element(
                    By.XPATH,
                    xpath,
                )
            )

        raise NoSuchElementException(
            "The decision did not include ref, css, or name."
        )

    def close(self):
        self.driver.quit()