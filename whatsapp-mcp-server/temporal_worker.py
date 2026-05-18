import asyncio
import logging
from temporalio.client import Client
from temporalio.worker import Worker

# Import our workflow and activities
from temporal_workflows import WhatsAppAutoReplyWorkflow
from temporal_activities import check_for_new_messages, generate_bespoke_reply, send_reply

async def main():
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # 1. Connect to the Temporal server (running in your Docker extension)
    # The default port is 7233
    client = await Client.connect("localhost:7233")

    # 2. Start a Worker that listens on a specific "Task Queue"
    # This queue name must match what you put in the Temporal UI
    worker = Worker(
        client,
        task_queue="whatsapp-queue",
        workflows=[WhatsAppAutoReplyWorkflow],
        activities=[check_for_new_messages, generate_bespoke_reply, send_reply],
    )
    
    print("Worker started! Listening on task_queue: 'whatsapp-queue'")
    print("You can now trigger this from the Temporal UI at localhost:8233")
    
    await worker.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nWorker stopped.")
