"""
Main entry point: polls Gmail, filters by allowed senders, sends each
new email body to Anthropic with a fixed prompt, and saves results to CSV.

Run with:  python main.py
Stop with: Ctrl+C
"""
import time
import traceback

import config
import gmail_client
import gemini_client
import storage


def load_senders():
    import json
    if os.path.exists("senders.json"):
        with open("senders.json") as f:
            return json.load(f).get("allowed_senders", [])
    return config.ALLOWED_SENDERS


def is_allowed(sender_email: str) -> bool:
    allowed = {s.lower() for s in load_senders()}
    return sender_email.lower() in allowed


def process_once(service, state):
    new_messages = gmail_client.fetch_new_messages(service, state)

    if not new_messages:
        print("No new messages.")
        return

    for msg in new_messages:
        sender = msg["sender_email"]
        subject = msg["subject"]

        if not is_allowed(sender):
            print(f"Skipping (not in allowlist): {sender} | {subject}")
            continue

        body = msg["body"].strip()
        if not body:
            print(f"Skipping (empty body): {sender} | {subject}")
            continue

        print(f"Processing email from {sender} | {subject}")
        try:
            output = gemini_client.run_prompt(body)
        except Exception as e:
            print(f"  ERROR calling Gemini API: {e}")
            continue

        storage.append_result(
            sender_email=sender,
            subject=subject,
            message=body,
            gemini_output=output,
        )
        print(f"  Saved result to {config.OUTPUT_CSV}")


def main():
    print("Authenticating with Gmail...")
    service = gmail_client.get_gmail_service()
    state = gmail_client.load_state()
    print("Authenticated. Starting poll loop "
          f"(every {config.POLL_INTERVAL_SECONDS}s). Press Ctrl+C to stop.")

    try:
        while True:
            try:
                process_once(service, state)
            except Exception:
                print("Error during poll cycle:")
                traceback.print_exc()
            finally:
                gmail_client.save_state(state)

            time.sleep(config.POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("\nStopped by user.")
        gmail_client.save_state(state)


if __name__ == "__main__":
    main()
