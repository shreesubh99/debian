from typing import Dict, Any, List, Callable
from src.tools import read_tools, write_tools

# Dictionary mapping tool names to actual functions
TOOL_REGISTRY: Dict[str, Callable] = {
    "get_customer": read_tools.get_customer,
    "get_customer_balance": read_tools.get_customer_balance,
    "get_booking_status": read_tools.get_booking_status,
    "get_ticket_details": read_tools.get_ticket_details,
    "get_customer_history": read_tools.get_customer_history,
    "get_available_services": read_tools.get_available_services,
    "enable_voice_mode": read_tools.enable_voice_mode,
    "search_trains_between_stations": read_tools.search_trains_between_stations,
    "get_live_train_status": read_tools.get_live_train_status,
    "get_seat_availability": read_tools.get_seat_availability,
    "log_user_correction": read_tools.log_user_correction,
    "get_customer_ledger_statement": read_tools.get_customer_ledger_statement,
    "get_currency_exchange_rates": read_tools.get_currency_exchange_rates,
    
    # Blocked write operations
    "create_booking": write_tools.create_booking,
    "cancel_booking": write_tools.cancel_booking,
    "process_refund": write_tools.process_refund,
    "create_transaction": write_tools.create_transaction,
    "update_transaction": write_tools.update_transaction,
    "delete_transaction": write_tools.delete_transaction,
    "modify_payment": write_tools.modify_payment,
    "modify_customer": write_tools.modify_customer,
    "send_whatsapp_message": write_tools.send_whatsapp_message,
    "send_email": write_tools.send_email,
}

# Standardized tool definitions for the LLMs (compatible with Gemini & Groq schemas)
TOOLS_DECLARATIONS: List[Dict[str, Any]] = [
    {
        "name": "get_customer",
        "description": "Look up customer profile information from Shree Shubh Travel by ID, customer code, or mobile number.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id_or_mobile": {
                    "type": "string",
                    "description": "The customer's ID, customer code (e.g. CUST-000001), or 10-digit mobile number."
                }
            },
            "required": ["customer_id_or_mobile"]
        }
    },
    {
        "name": "get_customer_balance",
        "description": "Look up outstanding/pending balance for a customer. Returns total balance and a list of pending bills.",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id_or_mobile": {
                    "type": "string",
                    "description": "The customer's ID, customer code, or 10-digit mobile number."
                }
            },
            "required": ["customer_id_or_mobile"]
        }
    },
    {
        "name": "get_booking_status",
        "description": "Check the travel status and payment status of a booking or PNR number.",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id_or_pnr": {
                    "type": "string",
                    "description": "The Booking ID or PNR number."
                }
            },
            "required": ["booking_id_or_pnr"]
        }
    },
    {
        "name": "get_ticket_details",
        "description": "Retrieve full ticket details like passenger count, class, route, train number, and dates for a PNR/booking.",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id_or_pnr": {
                    "type": "string",
                    "description": "The PNR number or Booking ID."
                }
            },
            "required": ["booking_id_or_pnr"]
        }
    },
    {
        "name": "get_customer_history",
        "description": "Fetch customer travel and payment transaction history (past bookings, completed payments).",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id_or_mobile": {
                    "type": "string",
                    "description": "The customer's ID, customer code, or mobile number."
                }
            },
            "required": ["customer_id_or_mobile"]
        }
    },
    {
        "name": "get_available_services",
        "description": "List the travel and tour service sectors offered by Shree Shubh Travel (e.g. Railway, Flight, Hotel, Forex, Tour Packages).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    
    # Write tools (declared so the model knows they exist, but will throw safety error when executed in testing)
    {
        "name": "create_booking",
        "description": "Create a new booking in the database (write operation).",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "service_type": {"type": "string"},
                "details": {"type": "string"}
            },
            "required": ["customer_id", "service_type"]
        }
    },
    {
        "name": "cancel_booking",
        "description": "Cancel an existing booking (write operation).",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id_or_pnr": {"type": "string"}
            },
            "required": ["booking_id_or_pnr"]
        }
    },
    {
        "name": "process_refund",
        "description": "Process refund for a booking or transaction (write operation).",
        "parameters": {
            "type": "object",
            "properties": {
                "booking_id_or_pnr": {"type": "string"},
                "refund_amount": {"type": "number"}
            },
            "required": ["booking_id_or_pnr", "refund_amount"]
        }
    },
    {
        "name": "enable_voice_mode",
        "description": "Enable or disable automatic voice/audio note responses for this chat session. Use this when the user requests voice notes, states they cannot read, or wants audio responses.",
        "parameters": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                    "description": "Set to true to enable voice note outputs for all future responses, or false to disable."
                }
            },
            "required": ["enabled"]
        }
    },
    {
        "name": "search_trains_between_stations",
        "description": "Find direct trains running between two station codes (e.g. from HWH to ASR).",
        "parameters": {
            "type": "object",
            "properties": {
                "from_station": {
                    "type": "string",
                    "description": "Source station code (e.g., 'HWH', 'NDLS')."
                },
                "to_station": {
                    "type": "string",
                    "description": "Destination station code (e.g., 'ASR', 'BCT')."
                },
                "date": {
                    "type": "string",
                    "description": "Journey date in DD-MM-YYYY format (optional)."
                }
            },
            "required": ["from_station", "to_station"]
        }
    },
    {
        "name": "get_live_train_status",
        "description": "Get real-time running status, delays, and current position for a 5-digit train number.",
        "parameters": {
            "type": "object",
            "properties": {
                "train_no": {
                    "type": "string",
                    "description": "5-digit train number (e.g., '13005', '12301')."
                },
                "date": {
                    "type": "string",
                    "description": "Journey date in DD-MM-YYYY format (optional)."
                }
            },
            "required": ["train_no"]
        }
    },
    {
        "name": "get_seat_availability",
        "description": "Check real-time seat availability status and fare for a specific train, date, class, and quota.",
        "parameters": {
            "type": "object",
            "properties": {
                "train_no": {
                    "type": "string",
                    "description": "5-digit train number (e.g., '13005')."
                },
                "from_station": {
                    "type": "string",
                    "description": "Source station code (e.g., 'HWH')."
                },
                "to_station": {
                    "type": "string",
                    "description": "Destination station code (e.g., 'ASR')."
                },
                "date": {
                    "type": "string",
                    "description": "Journey date in DD-MM-YYYY format (e.g., '15-04-2026')."
                },
                "travel_class": {
                    "type": "string",
                    "description": "Travel class code: '1A' | '2A' | '3A' | 'SL' | '3E' | 'CC' | '2S'."
                },
                "quota": {
                    "type": "string",
                    "description": "Quota code: 'GN' (General) | 'TQ' (Tatkal) | 'LD' (Ladies) | 'SS' (Lower Berth). Defaults to 'GN'."
                }
            },
            "required": ["train_no", "from_station", "to_station", "date", "travel_class"]
        }
    },
    {
        "name": "log_user_correction",
        "description": "Log when a user/customer corrects the agent's statements or database facts (e.g. incorrect balance, wrong date, PNR details). This saves the session and suggestion for verification and training accuracy improvements.",
        "parameters": {
            "type": "object",
            "properties": {
                "incorrect_fact": {
                    "type": "string",
                    "description": "The incorrect fact or statement that the agent made previously."
                },
                "user_correction_suggestion": {
                    "type": "string",
                    "description": "What the customer claims is the correct fact or information."
                }
            },
            "required": ["incorrect_fact", "user_correction_suggestion"]
        }
    },
    {
        "name": "get_customer_ledger_statement",
        "description": "Fetch customer ledger statement, total billing, payments, outstanding balance, and average payment delay statistics from a start date (e.g. 2026-08-01).",
        "parameters": {
            "type": "object",
            "properties": {
                "customer_id_or_mobile": {
                    "type": "string",
                    "description": "The customer's ID, customer code, or mobile number."
                },
                "start_date": {
                    "type": "string",
                    "description": "The start date for transaction records in YYYY-MM-DD format. Defaults to August 1st of the current year (e.g., '2026-08-01')."
                },
                "end_date": {
                    "type": "string",
                    "description": "The end date for transaction records in YYYY-MM-DD format (optional). E.g. '2026-08-15'."
                }
            },
            "required": ["customer_id_or_mobile"]
        }
    },
    {
        "name": "get_currency_exchange_rates",
        "description": "Get current buy/sell exchange rates for foreign currencies (USD, EUR, GBP, AED, SAR, etc.) at Shree Shubh Travel.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
]

def execute_tool(tool_name: str, args: Dict[str, Any], session_id: str = None) -> Any:
    """
    Looks up a tool by name in the TOOL_REGISTRY and executes it with args.
    Checks signature and dynamically injects session_id if accepted.
    No try-catch block here so errors propagate directly as requested.
    """
    if tool_name not in TOOL_REGISTRY:
        raise KeyError(f"Tool '{tool_name}' is not registered in the system.")
    
    tool_func = TOOL_REGISTRY[tool_name]
    
    import inspect
    sig = inspect.signature(tool_func)
    if "session_id" in sig.parameters:
        return tool_func(session_id=session_id, **args)
    else:
        return tool_func(**args)
