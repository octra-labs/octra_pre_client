#!/usr/bin/env python3
"""
Test script to validate automation logic without dependencies
"""
import json
import os
from datetime import datetime

# Mock the automation state functions
AUTOMATION_STATE_FILE = "automation_state.json"
DAILY_AMOUNT = 0.01
MAX_TOTAL_SENT = 1.0

def load_automation_state():
    """Load automation state from file"""
    try:
        if os.path.exists(AUTOMATION_STATE_FILE):
            with open(AUTOMATION_STATE_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return {
        'total_sent': 0.0,
        'last_send_date': None,
        'last_claim_check': None
    }

def save_automation_state(state):
    """Save automation state to file"""
    try:
        with open(AUTOMATION_STATE_FILE, 'w') as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"Error saving automation state: {e}")

def test_automation_logic():
    """Test the automation logic"""
    print("Testing automation logic...")
    
    # Test initial state
    state = load_automation_state()
    print(f"Initial state: {state}")
    
    # Test daily sending logic
    today = datetime.now().strftime('%Y-%m-%d')
    should_send = (
        state['last_send_date'] != today and
        state['total_sent'] < MAX_TOTAL_SENT
    )
    
    print(f"Should send today: {should_send}")
    print(f"Today's date: {today}")
    print(f"Last send date: {state['last_send_date']}")
    print(f"Total sent: {state['total_sent']:.6f} / {MAX_TOTAL_SENT}")
    print(f"Remaining: {max(0, MAX_TOTAL_SENT - state['total_sent']):.6f}")
    
    # Simulate sending
    if should_send:
        print("Simulating successful send...")
        state['total_sent'] += DAILY_AMOUNT
        state['last_send_date'] = today
        save_automation_state(state)
        print(f"Updated state: {state}")
    
    # Test limit reached
    if state['total_sent'] >= MAX_TOTAL_SENT:
        print("❌ Maximum limit reached!")
    else:
        print("✅ Can still send more")

if __name__ == "__main__":
    test_automation_logic()
