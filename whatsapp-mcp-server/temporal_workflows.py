from datetime import timedelta
from temporalio import workflow

# Import the activities (we use type hinting only to avoid circular imports if needed, 
# but for Temporal it's best to use string names or import them directly if safe)
with workflow.unsafe.imports_passed_through():
    from temporal_activities import check_for_new_messages, generate_bespoke_reply, send_reply

@workflow.defn
class WhatsAppAutoReplyWorkflow:
    @workflow.run
    async def run(self) -> str:
        # 1. Check for messages that need replies
        pending_chats = await workflow.execute_activity(
            check_for_new_messages,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        results = []
        for chat in pending_chats:
            # 2. Generate a bespoke reply for each chat
            reply_text = await workflow.execute_activity(
                generate_bespoke_reply,
                chat,
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            # 3. Send the reply
            success = await workflow.execute_activity(
                send_reply,
                args=[chat['jid'], reply_text],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            status = "Sent" if success else "Failed"
            results.append(f"Chat {chat['jid']}: {status}")
            
        return ", ".join(results) if results else "No new messages needing replies."
