import os
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

from exploratory_agent.browser import BrowserSession
from exploratory_agent.planner import Planner
from exploratory_agent.report import write_report


load_dotenv()

BASE_URL = os.getenv(
    "BASE_URL",
    "http://localhost:8000",
)
MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5.6",
)
HEADLESS = (
    os.getenv("HEADLESS", "false").lower()
    == "true"
)


def main():
    charter_path = Path("charters/cart.yaml")

    charter = charter_path.read_text(
        encoding="utf-8",
    )
    charter_data = yaml.safe_load(charter)

    max_actions = int(
        charter_data.get("max_actions", 25)
    )

    session_dir = (
        Path("sessions")
        / datetime.now().strftime("%Y%m%d-%H%M%S")
    )

    browser = BrowserSession(
        HEADLESS,
        session_dir / "evidence",
    )
    planner = Planner(MODEL)
    history = []

    try:
        browser.driver.get(BASE_URL)

        for _ in range(max_actions):
            observation = browser.observe()

            decision = planner.decide(
                charter,
                observation,
                history,
                BASE_URL,
            )

            history.append(
                {
                    "observation": (
                        observation.model_dump()
                    ),
                    "decision": (
                        decision.model_dump()
                    ),
                }
            )

            print(
                f"{decision.action}: "
                f"{decision.reason}"
            )

            if decision.action == "finish":
                break

            execution_error = browser.execute(
                decision,
                BASE_URL,
            )

            if execution_error:
                history[-1]["execution_error"] = (
                    execution_error
                )

                print(
                    f"Action could not be completed: "
                    f"{execution_error}"
                )

        report_path = write_report(
            session_dir,
            charter,
            charter_data,
            history,
        )

        print(f"Report: {report_path}")

    finally:
        browser.close()


if __name__ == "__main__":
    main()