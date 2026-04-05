DEFAULT_CONFIG = {
    # Model configuration
    "deep_think_model": "claude-sonnet-4-20250514",
    "quick_think_model": "claude-haiku-4-5-20251001",

    # Debate configuration
    "max_debate_rounds": 1,  # Bull/Bear debate iterations
    "max_risk_discuss_rounds": 1,  # Risk analysis debate iterations

    # Max turns per agent call (limits tool use loops)
    "analyst_max_turns": 10,
    "debate_max_turns": 3,
    "manager_max_turns": 3,

    # Budget limit per query (USD)
    "max_budget_usd": 10.0,
}
