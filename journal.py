import streamlit as st
import json
import os
from datetime import datetime
import uuid
from pathlib import Path
import base64
import re

# --- Configuration ---
DATA_FILE = 'journal_data.json'
IMAGE_DIR = 'trade_images'
PAGE_TITLE = "Streamlit Trading Journal"

# Instruments for the dropdown
INSTRUMENT_OPTIONS = [
    "Micro NASDAQ Futures", 
    "Micro ES Futures"
]

# Trade directions for the dropdown
DIRECTION_OPTIONS = [
    "Long",
    "Short"
]

# --- Fixed Cost Constants (Based on user's trading report for 1 contract round-turn) ---
# Total Commission per 1 round-turn contract (e.g., Broker's flat rate)
DEFAULT_COMMISSION_PER_CONTRACT = 0.78 
# Total Fees per 1 round-turn contract (Exchange, NFA, Clearing, etc.)
DEFAULT_FEES_PER_CONTRACT = 1.12      
# Total fixed cost per contract: 0.78 + 1.12 = 1.90 

# --- Data Persistence Functions ---

def ensure_image_directory():
    """Checks if the local directory for trade images exists and creates it if not."""
    path = Path(IMAGE_DIR)
    path.mkdir(exist_ok=True) # Creates the directory if it doesn't exist, does nothing otherwise.

def load_data():
    """Loads trade data from the local JSON file."""
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return []
    except json.JSONDecodeError:
        # File is corrupted or empty, treat as empty journal
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred while loading data: {e}")
        return []

def save_data(trades):
    """Saves the current list of trades back to the JSON file."""
    try:
        with open(DATA_FILE, 'w') as f:
            # indent=4 makes the JSON file human-readable for debugging/backup
            json.dump(trades, f, indent=4)
    except Exception as e:
        st.error(f"Error saving data: {e}. Check file permissions.")

# --- Utility Functions ---

def save_uploaded_file(uploaded_file):
    """Saves the uploaded file bytes to the local image directory with a unique name."""
    ensure_image_directory()
    
    # Create a unique filename
    extension = Path(uploaded_file.name).suffix
    unique_filename = f"{uuid.uuid4()}{extension}"
    file_path = Path(IMAGE_DIR) / unique_filename
    
    # Write the contents of the file to disk
    try:
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return str(file_path)
    except Exception as e:
        st.error(f"Error saving file: {e}")
        return None


def calculate_pnl(entry, exit, instrument, direction, contracts, commissions, fees):
    """
    Calculates the NET P&L in dollars, accounting for instrument point value,
    direction, contracts, commissions, and fees.
    """
    try:
        entry_price = float(entry)
        exit_price = float(exit)
        num_contracts = int(contracts)
        commissions = float(commissions)
        fees = float(fees)
    except (TypeError, ValueError):
        # If any input is invalid or missing, return 0 or an appropriate default
        return 0.0

    # 1. Determine the dollar value per point based on the instrument
    if "NASDAQ" in instrument:
        point_value = 2.00
    elif "ES Futures" in instrument:
        point_value = 5.00
    else:
        # Default for safety
        point_value = 1.00 

    # 2. Calculate the difference in price (points gained/lost)
    price_diff = exit_price - entry_price

    # 3. Adjust the P&L based on the trade direction (Long/Short)
    if direction == "Short":
        # Short trade: Profit if Entry > Exit. If price_diff (Exit - Entry) is positive, it's a loss.
        total_points = price_diff * -1 
    else: # Direction is "Long"
        # Long trade: Profit if Exit > Entry. price_diff (Exit - Entry) is directly the points.
        total_points = price_diff

    # 4. Calculate the GROSS dollar P&L
    gross_pnl = total_points * point_value * num_contracts
    
    # 5. Calculate the NET P&L
    net_pnl = gross_pnl - commissions - fees
    
    return round(net_pnl, 2)

# --- Streamlit Session State Handlers ---

def set_selected_trade(trade_id):
    """Callback function to set the current trade ID for viewing/editing."""
    st.session_state.selected_trade_id = trade_id

def start_new_trade():
    """Callback function to reset the form for logging a new trade."""
    st.session_state.selected_trade_id = None

def delete_selected_trade():
    """Handles the deletion of the currently selected trade and its associated image."""
    trade_id_to_delete = st.session_state.selected_trade_id
    if not trade_id_to_delete:
        return

    trades = st.session_state.trades
    
    # Find the trade and its index
    trade_index = next((i for i, trade in enumerate(trades) if trade['id'] == trade_id_to_delete), -1)

    if trade_index != -1:
        trade_to_delete = trades[trade_index]
        
        # 1. Delete the image file if it exists
        image_path = trade_to_delete.get('tradeImagePath')
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                st.warning(f"Could not delete image file: {e}")
        
        # 2. Delete the trade record from the list
        trades.pop(trade_index)
        
        # 3. Save the updated list to the JSON file
        save_data(trades)
        
        # 4. Reset the state to view a new trade
        st.session_state.selected_trade_id = None
        st.toast("Trade deleted successfully!")
        st.rerun() 

# --- UI Rendering - Trade List ---

def render_trade_list(trades):
    """Renders the list of trades in the Streamlit sidebar."""
    
    # Sort trades by date, most recent first
    sorted_trades = sorted(
        trades, 
        key=lambda x: datetime.strptime(x.get('date', '1970-01-01'), '%Y-%m-%d'), 
        reverse=True
    )
    
    st.sidebar.title("Journal History")
    
    st.sidebar.button("Log New Trade", on_click=start_new_trade, use_container_width=True)
    st.sidebar.markdown("---")
    
    if not sorted_trades:
        st.sidebar.info("No trades logged yet.")
        return

    # Loop through the sorted trades and render a clickable card for each
    for trade in sorted_trades:
        trade_id = trade['id']
        # The stored P&L is now the NET P&L
        pnl = trade.get('pnl', 0.0) 
        
        # Determine card color based on P&L
        if pnl > 0:
            color = "#16a34a" # Green for win
            sign = "+"
        elif pnl < 0:
            color = "#dc2626" # Red for loss
            sign = ""
        else:
            color = "#6b7280" # Grey/neutral
            sign = ""
            
        is_selected = st.session_state.selected_trade_id == trade_id
        
        # Use HTML/Markdown for styling the card
        card_style = f"""
            background-color: {'#27272a' if is_selected else '#18181b'};
            border: 2px solid {'#3b82f6' if is_selected else '#18181b'};
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 8px;
            cursor: pointer;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
        """
        
        card_content = f"""
            <div style="{card_style}">
                <p style="font-size: 14px; font-weight: bold; margin: 0; color: #d4d4d8;">
                    {trade.get('instrument', 'N/A')} - {trade.get('direction', 'N/A')}
                </p>
                <p style="font-size: 12px; margin: 0; color: #a1a1aa;">
                    {trade.get('date', 'N/A')} | {trade.get('contracts', 0)} Contracts
                </p>
                <h4 style="color: {color}; margin: 5px 0 0 0; font-size: 18px;">
                    {sign}${abs(pnl):,.2f} (NET)
                </h4>
            </div>
        """
        
        # Render the styled card
        st.sidebar.markdown(card_content, unsafe_allow_html=True)
        
        # Use a hidden button to capture the click event and call the callback
        if st.sidebar.button(
            'view', 
            key=f"select_{trade_id}", 
            on_click=set_selected_trade, 
            args=(trade_id,),
            help="Click to view trade details",
        ):
            pass 
        
        # Injects CSS to hide the visible button but keep the functionality
        st.markdown(
            """
            <style>
            .stSidebar button[kind="secondary"] {
                display: none;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

# --- UI Rendering - Trade Form ---

def render_trade_form():
    """Renders the main form for logging or editing a trade."""
    
    # 1. Determine if we are editing an existing trade or logging a new one
    selected_id = st.session_state.get('selected_trade_id')
    trades = st.session_state.trades
    is_new = selected_id is None
    
    selected_trade_data = {}
    trade_index = -1
    
    if not is_new:
        trade_index = next((i for i, trade in enumerate(trades) if trade['id'] == selected_id), -1)
        if trade_index != -1:
            selected_trade_data = trades[trade_index]

    # --- Setup Defaults for Form Population ---
    default_date = selected_trade_data.get('date', datetime.now().strftime('%Y-%m-%d'))
    default_instrument = selected_trade_data.get('instrument', INSTRUMENT_OPTIONS[0])
    default_direction = selected_trade_data.get('direction', DIRECTION_OPTIONS[0])
    default_contracts = selected_trade_data.get('contracts', 1)
    
    # Calculate default costs based on the contract count if it's a NEW trade,
    # or use saved values if EDITING an existing trade.
    if is_new:
        default_commissions = DEFAULT_COMMISSION_PER_CONTRACT * default_contracts
        default_fees = DEFAULT_FEES_PER_CONTRACT * default_contracts
    else:
        default_commissions = selected_trade_data.get('commissions', 0.0)
        default_fees = selected_trade_data.get('fees', 0.0)

    # Ensure defaults are floats for st.number_input
    default_commissions = float(default_commissions)
    default_fees = float(default_fees)
    
    # Use the index of the instrument/direction for the selectbox value
    instr_index = INSTRUMENT_OPTIONS.index(default_instrument) if default_instrument in INSTRUMENT_OPTIONS else 0
    dir_index = DIRECTION_OPTIONS.index(default_direction) if default_direction in DIRECTION_OPTIONS else 0

    st.header(("Log New Trade" if is_new else "Edit Trade"))
    
    # --- Start the Form ---
    with st.form(key='trade_form', clear_on_submit=False):
        
        # --- Row 1: Date, Instrument, Direction ---
        col1, col2, col3 = st.columns(3)
        with col1:
            date = st.date_input("Date", value=datetime.strptime(default_date, '%Y-%m-%d'))
        with col2:
            instrument = st.selectbox("Instrument", options=INSTRUMENT_OPTIONS, index=instr_index)
        with col3:
            direction = st.selectbox("Direction", options=DIRECTION_OPTIONS, index=dir_index)
            
        # --- Row 2: Contracts, Entry, Exit ---
        col4, col5, col6 = st.columns(3)
        with col4:
            # Added a unique key to allow for dynamic calculation if the user changes contracts on a new trade
            contracts = st.number_input("Number of Contracts", min_value=1, value=default_contracts, step=1, key="contracts_input")
        with col5:
            entry = st.text_input("Entry Price", value=selected_trade_data.get('entry', ''), placeholder="15000.25")
        with col6:
            exit = st.text_input("Exit Price", value=selected_trade_data.get('exit', ''), placeholder="15010.75")
        
        # --- NEW Row 3: Commissions and Fees ---
        st.subheader("Costs")
        
        # RE-CALCULATE DEFAULTS based on current contracts input for new trades
        # This allows the user to change contract count and see the default cost update, 
        # though the final submitted value is what matters.
        if is_new:
            calculated_commissions = DEFAULT_COMMISSION_PER_CONTRACT * contracts
            calculated_fees = DEFAULT_FEES_PER_CONTRACT * contracts
        else:
            calculated_commissions = default_commissions
            calculated_fees = default_fees

        col7, col8 = st.columns(2)
        with col7:
            commissions = st.number_input("Commissions Paid ($)", min_value=0.0, value=calculated_commissions, step=0.01, format="%.2f", key="commissions_input_final")
        with col8:
            fees = st.number_input("Fees/Slippage ($)", min_value=0.0, value=calculated_fees, step=0.01, format="%.2f", key="fees_input_final")

        st.info(f"The fixed cost for {contracts} contract(s) is $**{calculated_commissions + calculated_fees:.2f}** ($1.90 per contract). You can adjust the numbers above for slippage.")

        # --- Row 4: Setup and Notes ---
        st.subheader("Analysis")
        setup = st.text_input("Setup Used", 
                              value=selected_trade_data.get('setup', ''), placeholder="VWAP Rejection, S/R Break")
        
        notes = st.text_area("Trade Notes / Analysis", 
                             value=selected_trade_data.get('notes', ''), placeholder="Detailed analysis of the entry/exit decision.")

        # --- Row 5: Image Management (File Uploader) ---
        st.subheader("Trade Screenshot (Optional)")
        
        # Display existing image if available
        current_image_path = selected_trade_data.get('tradeImagePath')
        
        # Variables to track image state changes
        delete_current_image = False
        uploaded_file = None

        if current_image_path and os.path.exists(current_image_path):
            st.image(current_image_path, caption="Current Trade Image", use_column_width=True)
            # Add a checkbox to optionally delete the current image
            delete_current_image = st.checkbox("Delete current image", key="delete_image")
        
        # Use Streamlit's built-in file uploader
        uploaded_file = st.file_uploader(
            "Upload New Image (PNG/JPG)",
            type=["png", "jpg", "jpeg"],
            help="Upload a new screenshot. If a new file is uploaded, it will replace the current image.",
            key="new_image_upload"
        )
        
        st.markdown("---")
        
        # --- Submit Button ---
        submitted = st.form_submit_button(("Log Trade" if is_new else "Save Changes"), use_container_width=True, type="primary")

    # --- Form Submission Logic ---
    if submitted:
        # Calculate P&L using the submitted inputs (now includes commissions/fees)
        pnl_calculated = calculate_pnl(entry, exit, instrument, direction, contracts, commissions, fees)
        
        new_image_path = current_image_path
        
        # 1. Handle Image Deletion
        if not is_new and delete_current_image:
            if current_image_path and os.path.exists(current_image_path):
                try:
                    os.remove(current_image_path)
                    st.toast("Old image deleted.")
                except Exception:
                    pass
            new_image_path = None # Set path to None since it was deleted
            
        # 2. Handle New Image Upload
        if uploaded_file is not None:
            # Save the uploaded file to disk
            path_temp = save_uploaded_file(uploaded_file)
            
            if path_temp:
                # If we were editing an existing trade AND it had an old image (and wasn't just deleted), 
                # delete the old one to avoid orphans.
                if not is_new and current_image_path and current_image_path != new_image_path and os.path.exists(current_image_path):
                    try:
                        os.remove(current_image_path)
                    except Exception:
                        pass # Ignore minor errors here

                new_image_path = path_temp
            else:
                # If save_uploaded_file failed, path_temp is None. Stop submission.
                st.error("Image upload failed. Trade data not saved.")
                return


        # 3. Prepare the final trade dictionary
        trade_data = {
            'id': selected_id if not is_new else str(uuid.uuid4()),
            'date': date.strftime('%Y-%m-%d'),
            'instrument': instrument,
            'direction': direction,
            'contracts': contracts,
            'entry': entry,
            'exit': exit,
            'commissions': commissions, # New field
            'fees': fees,               # New field
            'pnl': pnl_calculated,      # This is now the NET P&L
            'setup': setup,
            'notes': notes,
            'tradeImagePath': new_image_path,
            'timestamp': datetime.now().isoformat()
        }

        # 4. Update the main trades list
        if is_new:
            st.session_state.trades.append(trade_data)
            st.toast("Trade Logged Successfully!")
        else:
            st.session_state.trades[trade_index] = trade_data
            st.toast("Trade Updated Successfully!")

        # 5. Save and Refresh
        save_data(st.session_state.trades)
        st.session_state.selected_trade_id = trade_data['id'] # Keep the updated trade selected
        st.rerun() 

    # --- Delete Button (Outside the form, only visible in edit mode) ---
    if not is_new:
        col_delete_out, _ = st.columns([1, 4])
        with col_delete_out:
            st.button(
                "Delete Trade", 
                on_click=delete_selected_trade, 
                type="secondary",
                use_container_width=True
            )

# --- Main Application Logic ---

def main():
    """Initializes the app, loads data, and orchestrates the UI rendering."""
    
    # 1. Page Configuration
    st.set_page_config(
        page_title=PAGE_TITLE,
        layout="wide", # Use wide layout for better space utilization
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS for dark theme look (removes header/footer, adds padding)
    st.markdown("""
        <style>
        .stApp {
            background-color: #0c0a09; /* Deep charcoal background */
            color: #d4d4d8; /* Light gray text */
        }
        .css-1d391kg {
            padding-top: 2rem;
            padding-bottom: 2rem;
        }
        .stButton>button {
            border-radius: 6px;
        }
        h1, h2, h3, h4 {
            color: #fafafa;
        }
        </style>
        """, unsafe_allow_html=True)

    # 2. Initialize Session State
    if 'trades' not in st.session_state:
        st.session_state.trades = load_data()
    
    # Initialize selected_trade_id to None if it doesn't exist
    if 'selected_trade_id' not in st.session_state:
        st.session_state.selected_trade_id = None
        
    # 3. Render UI Components
    
    # Left Sidebar: Trade List
    render_trade_list(st.session_state.trades)
    
    # Main Area: Trade Form / Detail View
    render_trade_form()

# 4. Run the Main Function
if __name__ == '__main__':
    main()
