def route_ticket_traditional(ticket_text):
    text = ticket_text.lower()
    
    billing_keywords = ["bill", "charge", "invoice", "pay", "credit card"]
    tech_keywords = ["broken", "error", "bug", "crash", "screen", "won't turn on"]
    sales_keywords = ["buy", "upgrade", "purchase", "pricing", "new"]
    
    if any(keyword in text for keyword in billing_keywords):
        return "Billing"
    elif any(keyword in text for keyword in tech_keywords):
        return "Technical Support"
    elif any(keyword in text for keyword in sales_keywords):
        return "Sales"
    else:
        return "Uncategorized (Human Review Required)"

if __name__ == "__main__":
    test_tickets = [
        "I was charged twice for my subscription this month.",
        "How much does it cost to upgrade to the enterprise plan?",
        "My app keeps crashing when I try to upload a photo.",
        "I am so mad! The new laptop I just bought has a broken screen, I want a refund right now!"
    ]
    
    print("--- Traditional Rule-Based Routing ---")
    for idx, ticket in enumerate(test_tickets):
        category = route_ticket_traditional(ticket)
        print(f"Ticket {idx + 1}: {category} | Text: '{ticket}'")