from src.db_connection import execute_query
from typing import Dict, Any, List, Optional

def get_customer(customer_id_or_mobile: str) -> Dict[str, Any]:
    """
    Look up a customer in the database by ID or mobile number.
    Returns customer details if found, or an empty dictionary.
    """
    # Safe query, read-only
    clean_digits = "".join(c for c in str(customer_id_or_mobile) if c.isdigit())
    last_10 = clean_digits[-10:] if len(clean_digits) >= 10 else customer_id_or_mobile
    with_country = "91" + last_10 if len(clean_digits) >= 10 else customer_id_or_mobile
    
    query = """
        SELECT id, customer_code, name, mobile, email, created_at, booking_source, origin_sector 
        FROM customers 
        WHERE mobile = %s OR mobile = %s OR mobile = %s OR id = %s OR customer_code = %s
    """
    rows = execute_query(query, (customer_id_or_mobile, last_10, with_country, customer_id_or_mobile, customer_id_or_mobile))
    
    if rows:
        return rows[0]
    return {}

def get_customer_balance(customer_id_or_mobile: str) -> Dict[str, Any]:
    """
    Get the outstanding balance for a customer.
    Returns a dictionary with outstanding balance and details.
    """
    clean_digits = "".join(c for c in str(customer_id_or_mobile) if c.isdigit())
    last_10 = clean_digits[-10:] if len(clean_digits) >= 10 else customer_id_or_mobile
    with_country = "91" + last_10 if len(clean_digits) >= 10 else customer_id_or_mobile

    # Get total outstanding balance from debtors (PENDING or PARTIAL status)
    # Total outstanding is defined as amount_due - settled_amount
    query_total = """
        SELECT SUM(amount_due - settled_amount) AS outstanding_balance 
        FROM debtors 
        WHERE (mobile = %s OR mobile = %s OR mobile = %s OR customer_id = %s) AND status IN ('PENDING', 'PARTIAL')
    """
    rows_total = execute_query(query_total, (customer_id_or_mobile, last_10, with_country, customer_id_or_mobile))
    
    # Get detailed list of outstanding transactions
    query_details = """
        SELECT debtor_id, pnr_no, amount_due, settled_amount, (amount_due - settled_amount) AS outstanding, 
               due_date, source, destination, train_no, travel_date, status, remarks 
        FROM debtors 
        WHERE (mobile = %s OR mobile = %s OR mobile = %s OR customer_id = %s) AND status IN ('PENDING', 'PARTIAL')
        ORDER BY due_date DESC
    """
    rows_details = execute_query(query_details, (customer_id_or_mobile, last_10, with_country, customer_id_or_mobile))
    
    # Get customer metadata for verification
    customer = get_customer(customer_id_or_mobile)
    
    balance = 0.0
    if rows_total and rows_total[0].get("outstanding_balance") is not None:
        balance = float(rows_total[0]["outstanding_balance"])
        
    return {
        "customer_id": customer.get("id"),
        "customer_name": customer.get("name", "Unknown"),
        "mobile": customer.get("mobile", customer_id_or_mobile),
        "outstanding_balance": balance,
        "pending_bills": rows_details or []
    }

def get_booking_status(booking_id_or_pnr: str) -> Dict[str, Any]:
    """
    Check booking or ticket status (e.g. is it cancelled, pending, or settled).
    """
    # Check ticket_transactions
    query_ticket = """
        SELECT ticket_id, ticket_no AS pnr_no, route, class, ticket_amount, ticket_type, 
               pnr_cancel, payment_mode, created_at, train_no, train_name, passenger_count, 
               book_date, travel_date, mobile, customer_id 
        FROM ticket_transactions 
        WHERE ticket_no = %s OR ticket_id = %s
    """
    rows_ticket = execute_query(query_ticket, (booking_id_or_pnr, booking_id_or_pnr))
    
    # Check outstanding payment status in debtors
    query_debtor = """
        SELECT debtor_id, debtor_name, mobile, amount_due, settled_amount, status, due_date, remarks 
        FROM debtors 
        WHERE pnr_no = %s
    """
    rows_debtor = execute_query(query_debtor, (booking_id_or_pnr,))
    
    if not rows_ticket and not rows_debtor:
        return {}
        
    ticket_info = rows_ticket[0] if rows_ticket else {}
    debtor_info = rows_debtor[0] if rows_debtor else {}
    
    # Consolidate status
    pnr_cancel = ticket_info.get("pnr_cancel", 0)
    ticket_type = ticket_info.get("ticket_type", "SALE")
    
    status = "Confirmed"
    if pnr_cancel == 1 or ticket_type == "CANCEL":
        status = "Cancelled"
    
    return {
        "pnr_no": ticket_info.get("pnr_no", booking_id_or_pnr),
        "ticket_status": status,
        "booking_details": ticket_info,
        "payment_status": debtor_info.get("status", "No Outstanding Record"),
        "amount_due": float(debtor_info.get("amount_due", 0.0)) if debtor_info else 0.0,
        "settled_amount": float(debtor_info.get("settled_amount", 0.0)) if debtor_info else 0.0,
        "outstanding": float(debtor_info.get("amount_due", 0.0) - debtor_info.get("settled_amount", 0.0)) if debtor_info else 0.0,
        "remarks": debtor_info.get("remarks", "")
    }

def get_ticket_details(booking_id_or_pnr: str) -> Dict[str, Any]:
    """
    Get full ticket details (train name, number, route, travel date, passenger count).
    """
    # This queries the ticket details table. In ytsk, it's ticket_transactions.
    return get_booking_status(booking_id_or_pnr)

def get_customer_history(customer_id_or_mobile: str) -> Dict[str, Any]:
    """
    Retrieve customer transaction and ticket history.
    """
    clean_digits = "".join(c for c in str(customer_id_or_mobile) if c.isdigit())
    last_10 = clean_digits[-10:] if len(clean_digits) >= 10 else customer_id_or_mobile
    with_country = "91" + last_10 if len(clean_digits) >= 10 else customer_id_or_mobile

    # Retrieve tickets
    query_tickets = """
        SELECT ticket_id, ticket_no AS pnr_no, route, class, ticket_amount, ticket_type, 
               train_no, train_name, travel_date, created_at 
        FROM ticket_transactions 
        WHERE mobile = %s OR mobile = %s OR mobile = %s OR customer_id = %s
        ORDER BY travel_date DESC
        LIMIT 10
    """
    rows_tickets = execute_query(query_tickets, (customer_id_or_mobile, last_10, with_country, customer_id_or_mobile))
    
    # Retrieve past ledger entries in debtors (settled or written off)
    query_past_debt = """
        SELECT debtor_id, pnr_no, amount_due, settled_amount, settled_date, status, remarks 
        FROM debtors 
        WHERE (mobile = %s OR mobile = %s OR mobile = %s OR customer_id = %s) AND status IN ('SETTLED', 'WRITTEN_OFF')
        ORDER BY settled_date DESC
        LIMIT 10
    """
    rows_past_debt = execute_query(query_past_debt, (customer_id_or_mobile, last_10, with_country, customer_id_or_mobile))
    
    customer = get_customer(customer_id_or_mobile)
    
    return {
        "customer_id": customer.get("id"),
        "customer_name": customer.get("name", "Unknown"),
        "tickets": rows_tickets or [],
        "payment_history": rows_past_debt or []
    }

def get_available_services() -> List[Dict[str, str]]:
    """
    Get services available at Shree Shubh Travel.
    """
    return [
        {
            "service": "Railway Ticket Booking",
            "description": "Authorized YTSK railway ticket reservations, upgrades, reissue, and cancellation services."
        },
        {
            "service": "Currency Exchange",
            "description": "Foreign currency buy and sell exchange services."
        },
        {
            "service": "Flight Tickets",
            "description": "Domestic and international flight inquiry and bookings."
        },
        {
            "service": "Hotel Reservation",
            "description": "Hotel accommodations booking across India and international destinations."
        },
        {
            "service": "Holiday Tours & Visas",
            "description": "Tailored tour packages and expert visa processing guidance."
        }
    ]

def enable_voice_mode(session_id: str, enabled: bool) -> Dict[str, Any]:
    """
    Enables or disables automatic voice/audio note responses for the current session.
    """
    from src.agent.memory import memory
    memory.update_context(session_id, "voice_mode", enabled)
    return {
        "status": "success",
        "voice_mode_enabled": enabled,
        "message": f"Voice mode has been {'enabled' if enabled else 'disabled'} successfully. All future responses in this session will automatically include voice audio notes."
    }

def search_trains_between_stations(from_station: str, to_station: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Search for trains running between two station codes (e.g. from HWH to ASR).
    """
    from src.config import Config
    from src.services.railkit import make_railkit_request, get_mock_trains
    
    if getattr(Config, "RAILKIT_API_KEY", None):
        path = f"/api/searchTrainBetweenStations/{from_station.upper()}/{to_station.upper()}"
        params = {}
        if date:
            params["date"] = date
        res = make_railkit_request(path, params)
        if res.get("success"):
            return {
                "success": True,
                "trains": res["data"]
            }
        else:
            return {
                "success": False,
                "error": res.get("error", "Failed to retrieve train search result.")
            }
    else:
        return {
            "success": True,
            "mode": "simulation",
            "trains": get_mock_trains(from_station, to_station)
        }

def get_live_train_status(train_no: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the live running status and current position of a 5-digit train number.
    """
    from src.config import Config
    from src.services.railkit import make_railkit_request, get_mock_live_status
    
    if getattr(Config, "RAILKIT_API_KEY", None):
        path = f"/api/trackTrain/{train_no}"
        if date:
            path += f"/{date}"
        res = make_railkit_request(path)
        if res.get("success"):
            return {
                "success": True,
                "status": res["data"]
            }
        else:
            return {
                "success": False,
                "error": res.get("error", "Failed to retrieve live running status.")
            }
    else:
        return {
            "success": True,
            "mode": "simulation",
            "status": get_mock_live_status(train_no)
        }

def get_seat_availability(
    train_no: str, 
    from_station: str, 
    to_station: str, 
    date: str, 
    travel_class: str, 
    quota: str = "GN"
) -> Dict[str, Any]:
    """
    Check real-time seat availability and status for a train, class, and date.
    Classes: '1A' | '2A' | '3A' | 'SL' | '3E' | 'CC' | '2S'
    Quotas: 'GN' (General) | 'TQ' (Tatkal) | 'LD' (Ladies) | 'SS' (Lower Berth)
    """
    from src.config import Config
    from src.services.railkit import make_railkit_request, get_mock_availability
    
    if getattr(Config, "RAILKIT_API_KEY", None):
        t_no = str(train_no).strip()
        frm = str(from_station).strip().upper()
        to = str(to_station).strip().upper()
        dt = str(date).strip()
        cls = str(travel_class).strip().upper()
        qt = str(quota).strip().upper()
        
        path = f"/api/getAvailability/{t_no}/{frm}/{to}/{dt}/{cls}/{qt}"
        res = make_railkit_request(path)
        if res.get("success"):
            return {
                "success": True,
                "availability": res["data"]
            }
        else:
            return {
                "success": False,
                "error": res.get("error", "Failed to retrieve seat availability.")
            }
    else:
        return {
            "success": True,
            "mode": "simulation",
            "availability": get_mock_availability(train_no, travel_class)
        }

def log_user_correction(session_id: str, incorrect_fact: str, user_correction_suggestion: str) -> Dict[str, Any]:
    """
    Logs when a customer corrects the agent's statements or database facts.
    Saves the session_id, incorrect fact, and customer's suggestion for analysis and fine-tuning.
    """
    import os
    import json
    import time
    
    dir_path = os.path.join(os.getcwd(), "conversations")
    os.makedirs(dir_path, exist_ok=True)
    file_path = os.path.join(dir_path, "user_corrections.json")
    
    entry = {
        "session_id": session_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "incorrect_fact": incorrect_fact,
        "user_correction_suggestion": user_correction_suggestion,
        "status": "pending_verification"
    }
    
    # Load existing corrections
    corrections = []
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    corrections = loaded
        except Exception:
            pass
            
    corrections.append(entry)
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(corrections, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Failed to save user correction: {e}")
        
    return {
        "status": "success",
        "message": "User correction logged successfully. Our operations team is reviewing this to verify and update the system accuracy."
    }

def get_customer_ledger_statement(customer_id_or_mobile: str, start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    Retrieve customer ledger statement starting from a specific date (defaults to August 1st of current year)
    and up to an optional end date. Calculates billing, payments, outstanding, and clearing times.
    """
    import datetime
    import time
    
    if not start_date:
        curr_year = datetime.datetime.now().year
        start_date = f"{curr_year}-08-01"
        
    # Get customer details
    customer = get_customer(customer_id_or_mobile)
    cust_id = customer.get("id")
    cust_mobile = customer.get("mobile", customer_id_or_mobile)
    
    if not cust_id:
        return {"error": "Customer not found."}
        
    # Query all debtors transactions since start_date and up to end_date
    if end_date:
        query = """
            SELECT debtor_id, pnr_no, amount_due, settled_amount, created_at, settled_date, status, remarks
            FROM debtors
            WHERE (mobile = %s OR customer_id = %s) AND created_at >= %s AND created_at <= %s
            ORDER BY created_at ASC
        """
        rows = execute_query(query, (cust_mobile, cust_id, start_date, end_date))
    else:
        query = """
            SELECT debtor_id, pnr_no, amount_due, settled_amount, created_at, settled_date, status, remarks
            FROM debtors
            WHERE (mobile = %s OR customer_id = %s) AND created_at >= %s
            ORDER BY created_at ASC
        """
        rows = execute_query(query, (cust_mobile, cust_id, start_date))
    
    total_billing = 0.0
    total_payment = 0.0
    outstanding = 0.0
    
    cleared_bills_count = 0
    total_days_to_clear = 0
    
    statement_entries = []
    
    for r in rows:
        amount_due = float(r.get("amount_due") or 0.0)
        settled_amount = float(r.get("settled_amount") or 0.0)
        status = r.get("status", "PENDING")
        created_at = r.get("created_at")
        settled_date = r.get("settled_date")
        
        total_billing += amount_due
        total_payment += settled_amount
        
        # Calculate days to clear
        if status == "SETTLED" and created_at and settled_date:
            try:
                # Convert to datetime date if they are datetime objects
                c_date = created_at.date() if hasattr(created_at, 'date') else datetime.datetime.strptime(str(created_at)[:10], "%Y-%m-%d").date()
                s_date = settled_date.date() if hasattr(settled_date, 'date') else datetime.datetime.strptime(str(settled_date)[:10], "%Y-%m-%d").date()
                diff_days = (s_date - c_date).days
                total_days_to_clear += max(0, diff_days)
                cleared_bills_count += 1
            except Exception:
                pass
                
        statement_entries.append({
            "debtor_id": r.get("debtor_id"),
            "pnr_no": r.get("pnr_no"),
            "date": str(created_at)[:10] if created_at else "N/A",
            "amount_due": amount_due,
            "settled_amount": settled_amount,
            "settled_date": str(settled_date)[:10] if settled_date else "N/A",
            "status": status,
            "remarks": r.get("remarks")
        })
        
    outstanding = total_billing - total_payment
    
    avg_clear_days = 0.0
    if cleared_bills_count > 0:
        avg_clear_days = round(total_days_to_clear / cleared_bills_count, 1)
        
    return {
        "customer_id": cust_id,
        "customer_name": customer.get("name", "Unknown"),
        "start_date": start_date,
        "total_billing": total_billing,
        "total_payment": total_payment,
        "outstanding": outstanding,
        "cleared_bills_count": cleared_bills_count,
        "avg_due_clear_days": avg_clear_days,
        "entries": statement_entries
    }

def get_currency_exchange_rates() -> Dict[str, Any]:
    """
    Get live foreign currency buy/sell exchange rates at Shree Shubh Travel.
    """
    # Check if there is a currency_rates table in the database, if not default to mock rates
    query = "SELECT currency_code, currency_name, buy_rate, sell_rate FROM currency_rates"
    try:
        rows = execute_query(query)
        if rows:
            return {"success": True, "rates": rows}
    except Exception:
        pass
        
    # Fallback to standard mock rates for currency exchange
    return {
        "success": True,
        "mode": "simulation",
        "rates": [
            {"currency_code": "USD", "currency_name": "US Dollar", "buy_rate": 83.20, "sell_rate": 84.10},
            {"currency_code": "EUR", "currency_name": "Euro", "buy_rate": 89.50, "sell_rate": 90.70},
            {"currency_code": "GBP", "currency_name": "British Pound", "buy_rate": 104.80, "sell_rate": 106.20},
            {"currency_code": "AED", "currency_name": "UAE Dirham", "buy_rate": 22.50, "sell_rate": 23.10},
            {"currency_code": "SAR", "currency_name": "Saudi Riyal", "buy_rate": 22.10, "sell_rate": 22.70},
            {"currency_code": "CAD", "currency_name": "Canadian Dollar", "buy_rate": 60.80, "sell_rate": 61.90},
            {"currency_code": "AUD", "currency_name": "Australian Dollar", "buy_rate": 54.20, "sell_rate": 55.40}
        ]
    }

