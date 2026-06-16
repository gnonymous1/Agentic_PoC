import logging

logger = logging.getLogger(__name__)


class TokenBudgetExceeded(Exception):
    def __init__(self, budget_type: str, current: int, limit: int):
        self.budget_type = budget_type
        self.current = current
        self.limit = limit
        super().__init__(
            f"Token budget '{budget_type}' exceeded: {current} > {limit}"
        )


class TokenBudget:
    def __init__(
        self,
        max_input: int = 10000,
        max_output: int = 20000,
        max_total: int = 50000,
    ):
        self.max_input = max_input
        self.max_output = max_output
        self.max_total = max_total
        self._input_tokens = 0
        self._output_tokens = 0

    def check_input(self, tokens: int) -> None:
        self._input_tokens += tokens
        if self._input_tokens > self.max_input:
            raise TokenBudgetExceeded("input", self._input_tokens, self.max_input)

    def check_output(self, tokens: int) -> None:
        self._output_tokens += tokens
        if self._output_tokens > self.max_output:
            raise TokenBudgetExceeded("output", self._output_tokens, self.max_output)

    @property
    def total_tokens(self) -> int:
        return self._input_tokens + self._output_tokens

    def reset(self) -> None:
        logger.info(
            "Resetting token budget (was %d input / %d output)",
            self._input_tokens,
            self._output_tokens,
        )
        self._input_tokens = 0
        self._output_tokens = 0
