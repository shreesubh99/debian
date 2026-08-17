from src.config import Config

class SafetyViolationError(PermissionError):
    """
    Exception raised when a write tool is called in testing/read-only mode.
    """
    pass

def check_write_permission(action_name: str):
    if Config.AGENT_MODE == "testing":
        raise SafetyViolationError(
            f"Write operation '{action_name}' blocked! Agent is in TESTING MODE (Read-Only). "
            f"No database inserts, updates, deletes, or actual external alerts are permitted."
        )

# Blocked Write Tools
def create_booking(*args, **kwargs):
    check_write_permission("create_booking")

def cancel_booking(*args, **kwargs):
    check_write_permission("cancel_booking")

def process_refund(*args, **kwargs):
    check_write_permission("process_refund")

def create_transaction(*args, **kwargs):
    check_write_permission("create_transaction")

def update_transaction(*args, **kwargs):
    check_write_permission("update_transaction")

def delete_transaction(*args, **kwargs):
    check_write_permission("delete_transaction")

def modify_payment(*args, **kwargs):
    check_write_permission("modify_payment")

def modify_customer(*args, **kwargs):
    check_write_permission("modify_customer")

def send_whatsapp_message(*args, **kwargs):
    check_write_permission("send_whatsapp_message")

def send_email(*args, **kwargs):
    check_write_permission("send_email")
