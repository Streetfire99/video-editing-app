"""
Dashboard Page

This Streamlit app displays a dashboard with key metrics and visualizations.
"""

import streamlit as st
import pandas as pd
from utils import get_data, initialize_session_state, logger
import traceback

def main():
    logger.info("Starting Dashboard page")
    try:
        st.set_page_config(
            page_title="Dashboard",
            page_icon="📊",
            layout="wide"
        )

        st.title("📊 Dashboard")

        # Initialize session state
        initialize_session_state()

        # Get all data
        logger.info("Fetching data for dashboard")
        try:
            contract_data = get_data("contratti")
            property_data = get_data("appartamenti")
            
            # Handle None values
            if contract_data is None:
                contract_data = pd.DataFrame()
            if property_data is None:
                property_data = pd.DataFrame()
                
            logger.info(f"Retrieved {len(contract_data)} contract records and {len(property_data)} property records")
        except Exception as e:
            logger.error(f"Error fetching data: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            st.error("Error loading data")
            return

        # Display metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Contracts", len(contract_data))
            logger.info("Displayed total contracts metric")
        
        with col2:
            st.metric("Total Properties", len(property_data))
            logger.info("Displayed total properties metric")
        
        with col3:
            active_contracts = len([c for c in contract_data if c.get("stato", "").lower() in ["pubblicato", "in progress"]])
            st.metric("Active Contracts", active_contracts)
            logger.info("Displayed active contracts metric")

        # Navigation Button
        if st.button("🏠 Back to Home"):
            logger.info("Navigating back to Home page")
            st.switch_page("../home.py")

    except Exception as e:
        logger.error(f"Unexpected error in main function: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        st.error("Si è verificato un errore imprevisto. Controlla i log per maggiori dettagli.")

if __name__ == "__main__":
    main() 