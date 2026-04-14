"""FDWA Autonomous Twitter Agent - Continuous Scheduler.

This script runs the FDWA agent continuously at specified intervals.
Set it and forget it - the agent will research trends and post tweets automatically.
"""

import logging
import time

import schedule

from src.agent.graph import graph

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('fdwa_agent.log'),
        logging.StreamHandler()
    ]
)

def run_fdwa_agent():
    """Execute the FDWA agent once."""
    try:
        logging.info("🤖 Starting FDWA Agent execution...")
        
        # Run the autonomous agent
        final_state = graph.invoke({})
        
        # Log results
        tweet = final_state.get('tweet_text', 'N/A')
        post_url = final_state.get('post_url', 'N/A')
        error = final_state.get('error')
        
        if error:
            logging.error(f"❌ Agent failed: {error}")
        else:
            logging.info(f"✅ Tweet posted: {tweet[:100]}...")
            logging.info(f"🔗 URL: {post_url}")
            
    except Exception as e:
        logging.error(f"❌ Critical error: {e}")

def start_autonomous_agent():
    """Start the continuous autonomous agent."""
    # Schedule options - uncomment the one you want:
    
    # Every 2 hours (recommended for active engagement)
    schedule.every(2).hours.do(run_fdwa_agent)
    
    # Every 4 hours (moderate posting)
    # schedule.every(4).hours.do(run_fdwa_agent)
    
    # Every 6 hours (conservative posting)
    # schedule.every(6).hours.do(run_fdwa_agent)
    
    # Specific times (business hours posting)
    # schedule.every().day.at("09:00").do(run_fdwa_agent)  # 9 AM
    # schedule.every().day.at("13:00").do(run_fdwa_agent)  # 1 PM  
    # schedule.every().day.at("17:00").do(run_fdwa_agent)  # 5 PM
    
    logging.info("🚀 FDWA Autonomous Agent started!")
    logging.info("📅 Schedule: Every 2 hours")
    logging.info("⏹️  Press Ctrl+C to stop")
    
    # Run once immediately
    run_fdwa_agent()
    
    # Keep running scheduled tasks
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    try:
        start_autonomous_agent()
    except KeyboardInterrupt:
        logging.info("🛑 Agent stopped by user")
    except Exception as e:
        logging.error(f"💥 Agent crashed: {e}")