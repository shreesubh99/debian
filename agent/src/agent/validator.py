import re
from typing import List, Dict, Any

class ResponseValidationError(ValueError):
    """
    Raised when the agent's generated response fails safety or validation criteria.
    """
    pass

def validate_agent_response(
    response_text: str,
    called_tools: List[str],
    session_history: List[Dict[str, Any]]
) -> str:
    """
    Validates the generated response for:
    - Hallucinated balance / numbers when no balance tool was called.
    - System prompt / internal architecture leakage.
    - False promises about booking confirmation.
    """
    response_lower = response_text.lower()
    
    # 0. ABSOLUTE CREDENTIAL PROTECTION
    from src.config import Config
    for credential in [Config.GEMINI_API_KEY, Config.GROQ_API_KEY]:
        if credential and len(credential) > 5 and credential in response_text:
            raise ResponseValidationError("Security Validation Failed: Response contains raw API credentials.")

    # 1. Check for Internal Information Leakage (Bypass if it is a legitimate rejection response)
    rejection_phrases = [
        "unable to share", 
        "policies ke tahat", 
        "share nahi kar sakti", 
        "not authorized to share",
        "sensitive information",
        "prakar ki details",
        "rejection policies"
    ]
    is_rejection = any(phrase in response_lower for phrase in rejection_phrases)
    
    if not is_rejection:
        leaked_terms = ["system prompt", "api key", "gemini_api_key", "groq_api_key", "database schema", "sql query"]
        for term in leaked_terms:
            if term in response_lower:
                raise ResponseValidationError(
                    f"Security Validation Failed: Response contains internal system terminology '{term}'."
                )

    # 2. Check for Hallucinated Balances
    # If the response contains security rejection keywords, bypass
    if "unable to share internal system information" in response_lower or is_rejection:
        return response_text

    # We only check if the agent mentions outstanding/balance and includes potential price/balance numbers
    balance_terms = ["outstanding", "balance", "payment", "due amount", "debtor"]
    financial_pattern = r"(?:rs\.?|rupees|₹|\bamt\b)\s*\d+"
    
    has_financial_mention = any(term in response_lower for term in balance_terms) or re.search(financial_pattern, response_lower)
    
    # Extract numbers of length 1 to 6 (ignoring 10-digit mobile numbers)
    small_numbers = re.findall(r"\b\d{1,6}(?:\.\d{1,2})?\b", response_text)
    has_small_numbers = len(small_numbers) > 0
    
    if has_financial_mention and has_small_numbers:
        # Check if tools retrieving balances / ticket financials were called
        balance_tools = [
            "get_customer_balance", 
            "get_booking_status", 
            "get_ticket_details", 
            "get_customer_history", 
            "get_customer_ledger_statement", 
            "get_currency_exchange_rates"
        ]
        if not any(tool in called_tools for tool in balance_tools):
            # Check if history already had this balance (to allow follow ups), if not, raise error
            had_prior_balance_data = False
            for prev_msg in session_history:
                if prev_msg.get("role") == "tool" and prev_msg.get("tool_name") in balance_tools:
                    had_prior_balance_data = True
                    break
            
            if not had_prior_balance_data:
                raise ResponseValidationError(
                    "Factual Validation Failed: Agent generated financial/balance details with numbers "
                    "but no database lookup tool (get_customer_balance/get_booking_status/get_ticket_details) was executed."
                )

    # 3. Check for False Promises
    guarantee_terms = ["definitely confirm", "guarantee", "will confirm", "hundred percent confirmed", "surely confirm"]
    for term in guarantee_terms:
        if term in response_lower:
            # If the database booking status doesn't confirm it, we shouldn't guarantee it.
            # We raise a warning or validation error.
            raise ResponseValidationError(
                f"Safety Validation Failed: Agent used unverified strong promise language '{term}'."
            )

    return response_text
