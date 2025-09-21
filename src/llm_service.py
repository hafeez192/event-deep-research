import asyncio
import inspect
import logging
import subprocess
import time
from typing import Any

try:
    import psutil
except ImportError:
    psutil = None

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class LLMWithTemperatureCheck:
    """A dynamic proxy wrapper that adds a CPU temperature check before any
    call to the underlying LLM. Forwards all attributes and methods.
    """

    def __init__(
        self,
        llm_instance: BaseChatModel,
        temp_threshold: float = 85.0,
        wait_seconds: int = 2,
    ):
        self._llm = llm_instance
        self.temp_threshold = temp_threshold
        self.wait_seconds = wait_seconds

    def _get_cpu_temperature(self):
        """Get the current CPU temperature using smctemp command.
        Retries until the output is not 40, which seems to be a bug.
        """
        while True:
            try:
                temp_output = subprocess.check_output(
                    "smctemp -c -i25 -n180 -f", shell=True, text=True
                )
                # Extract the temperature value from the output
                temp_value = float(temp_output.strip())

                if temp_value == 40:  # buggy reading, retry
                    logging.warning("Got temperature=40 (buggy). Retrying...")
                    time.sleep(0.1)  # small delay before retry
                    continue

                logging.info(f"Current temperature is: {temp_value}")
                return temp_value

            except (subprocess.SubprocessError, ValueError) as e:
                logging.error(f"Error getting temperature: {e}")
                return 0  # Return a safe value if temperature check fails

    def __getattr__(self, name: str) -> Any:
        original_attr = getattr(self._llm, name)

        if not callable(original_attr):
            return original_attr

        if inspect.iscoroutinefunction(original_attr):

            async def async_wrapper(*args, **kwargs):
                while (
                    temp := self._get_cpu_temperature()
                ) and temp > self.temp_threshold:
                    logging.warning(
                        f"CPU temp high ({temp:.1f}°C). Waiting {self.wait_seconds}s..."
                    )
                    await asyncio.sleep(self.wait_seconds)
                return await original_attr(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                while (
                    temp := self._get_cpu_temperature()
                ) and temp > self.temp_threshold:
                    logging.warning(
                        f"CPU temp high ({temp:.1f}°C). Waiting {self.wait_seconds}s..."
                    )
                    time.sleep(self.wait_seconds)
                return original_attr(*args, **kwargs)

            return sync_wrapper


def get_llm(model_name: str, **kwargs: Any) -> LLMWithTemperatureCheck:
    """Get LLM service wrapped with temperature checking."""
    original_llm = init_chat_model(temperature=0, model=model_name, **kwargs)
    return LLMWithTemperatureCheck(original_llm)
