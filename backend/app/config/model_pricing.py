"""
app/config/model_pricing.py

Centralized pricing configuration for LLM models.
Prices are represented in USD per 1,000,000 (1M) tokens.
"""

MODEL_PRICING = {
    # Gemini models
    "gemini-1.5-flash": {
        "input_per_1m_tokens": 0.075,
        "output_per_1m_tokens": 0.30
    },
    "gemini-1.5-pro": {
        "input_per_1m_tokens": 1.25,
        "output_per_1m_tokens": 5.00
    },
    "gemini-2.0-flash": {
        "input_per_1m_tokens": 0.10,
        "output_per_1m_tokens": 0.40
    },
    "gemini-2.5-flash": {
        "input_per_1m_tokens": 0.15,
        "output_per_1m_tokens": 0.60
    },
    "gemini-3.0-flash": {
        "input_per_1m_tokens": 0.20,
        "output_per_1m_tokens": 0.80
    },
    "gemini-3.5-flash": {
        "input_per_1m_tokens": 0.25,
        "output_per_1m_tokens": 1.00
    },

    # OpenAI models
    "gpt-4o": {
        "input_per_1m_tokens": 2.50,
        "output_per_1m_tokens": 10.00
    },
    "gpt-4o-mini": {
        "input_per_1m_tokens": 0.15,
        "output_per_1m_tokens": 0.60
    },
    "gpt-5.4-mini": {
        "input_per_1m_tokens": 0.15,
        "output_per_1m_tokens": 0.60
    },

    # Serper (per 1,000 searches is ~$1.00 - so per request is $0.001)
    # This is a flat rate per request, not token-based.
    "serper": {
        "cost_per_request": 0.001
    }
}
