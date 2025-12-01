import streamlit as st
import json
import os
from datetime import datetime
import uuid
from pathlib import Path
import re

# --- Configuration ---
# NOTE: The data and image storage functions remain the same for stability.
DATA_FILE = 'journal_data.json'
IMAGE_DIR = 'trade_images'
PAGE_TITLE = "The Zen Trade Journal"

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

# --- Fixed Cost Constants ---
DEFAULT_COMMISSION_PER_CONTRACT = 0.78 
DEFAULT_FEES_PER_CONTRACT = 1.12      

# --- Data Persistence Functions (Unchanged for stability) ---

def ensure_image_directory():
    path = Path(IMAGE_DIR)
    path.mkdir(exist_ok=True)

def load_data():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'r') as f:
                return json.load(f)
        return []
    except json.JSONDecodeError:
        return []
    except Exception as e:
        st.error(f"An unexpected error occurred while loading data: {e}")
        return []

def save_data(trades):
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(trades, f, indent=4)
    except Exception as e:
        st.error(f"Error saving data: {e}. Check file permissions.")

def save_uploaded_file(uploaded_file):
    ensure_image_directory()
    extension = Path(uploaded_file.name).suffix
    unique_filename = f"{uuid.uuid4()}{extension}"
    file_path = Path(IMAGE_DIR) / unique_filename
    
    try:
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return str(file_path)
    except Exception as e:
        st.error(f"Error saving file: {e}")
        return None

def calculate_pnl(entry, exit, instrument, direction, contracts, commissions, fees):
    try:
        entry_price = float(entry)
        exit_price = float(exit)
        num_contracts = int(contracts)
        commissions = float(commissions)
        fees = float(fees)
    except (TypeError, ValueError):
        return 0.0

    if "NASDAQ" in instrument:
        point_value = 2.00
    elif "ES Futures" in instrument:
        point_value = 5.00
    else:
        point_value = 1.00 

    price_diff = exit_price - entry_price

    if direction == "Short":
        total_points = price_diff * -1 
    else:
        total_points = price_diff

    gross_pnl = total_points * point_value * num_contracts
    net_pnl = gross_pnl - commissions - fees
    
    return round(net_pnl, 2)

# --- Streamlit Session State Handlers (Unchanged) ---

def set_selected_trade(trade_id):
    st.session_state.selected_trade_id = trade_id

def start_new_trade():
    st.session_state.selected_trade_id = None

def delete_selected_trade():
    trade_id_to_delete = st.session_state.selected_trade_id
    if not trade_id_to_delete:
        return

    trades = st.session_state.trades
    trade_index = next((i for i, trade in enumerate(trades) if trade['id'] == trade_id_to_delete), -1)

    if trade_index != -1:
        trade_to_delete = trades[trade_index]
        image_path = trade_to_delete.get('tradeImagePath')
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except Exception as e:
                st.warning(f"Could not delete image file: {e}")
        
        trades.pop(trade_index)
        save_data(trades)
        st.session_state.selected_trade_id = None
        st.toast("Trade deleted successfully!")
        st.rerun() 


# --- UI Rendering - Trade List (The Minimalist Sidebar) ---

def render_trade_list(trades):
    """Renders the list of trades with a minimalist, high-contrast style."""
    
    sorted_trades = sorted(
        trades, 
        key=lambda x: datetime.strptime(x.get('date', '1970-01-01'), '%Y-%m-%d'), 
        reverse=True
    )
    
    st.sidebar.title(PAGE_TITLE)
    
    # Use a high-contrast primary button for the main action
    if st.sidebar.button("Log New Trade", on_click=start_new_trade, use_container_width=True, type="primary"):
        pass

    st.sidebar.markdown("<hr style='border-top: 1px solid #2e2e2e; margin: 15px 0;'>", unsafe_allow_html=True)
    
    if not sorted_trades:
        st.sidebar.markdown("<p style='color: #a1a1aa; font-style: italic;'>No trades logged yet.</p>", unsafe_allow_html=True)
        return

    for trade in sorted_trades:
        trade_id = trade['id']
        pnl = trade.get('pnl', 0.0) 
        
        # Determine color (Gold for Win, Red for Loss, Gray for Break-even)
        if pnl > 0:
            color = "#f59e0b" # Amber/Gold for positive PnL (Elegance)
            sign = "+"
        elif pnl < 0:
            color = "#dc2626" # Red for loss
            sign = ""
        else:
            color = "#52525b" # Gray/neutral
            sign = ""
            
        is_selected = st.session_state.selected_trade_id == trade_id
        
        # Minimalist Card Styling
        card_style = f"""
            background-color: {'#18181b' if is_selected else '#0c0a09'};
            border-left: 3px solid {'#3b82f6' if is_selected else 'transparent'};
            padding: 10px 10px 10px 15px;
            margin-bottom: 5px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.2s;
        """
        
        card_content = f"""
            <div style="{card_style}">
                <p style="font-size: 14px; font-weight: 500; margin: 0; color: #d4d4d8;">
                    {trade.get('instrument', 'N/A')} ({trade.get('direction', 'N/A')})
                </p>
                <p style="font-size: 11px; margin: 2px 0; color: #71717a;">
                    {trade.get('date', 'N/A')} | {trade.get('contracts', 0)} Contracts
                </p>
                <h4 style="color: {color}; margin: 5px 0 0 0; font-size: 18px; font-weight: 600;">
                    {sign}${abs(pnl):,.2f} (NET)
                </h4>
            </div>
        """
        
        # Display the custom HTML card
        st.sidebar.markdown(card_content, unsafe_allow_html=True)
        
        # Invisible button to capture the click event
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


# --- UI Rendering - Trade Form (The Focused Content Area) ---

def render_trade_form():
    """Renders the main form with clean sections and focus."""
    
    selected_id = st.session_state.get('selected_trade_id')
    trades = st.session_state.trades
    is_new = selected_id is None
    
    selected_trade_data = {}
    trade_index = -1
    
    if not is_new:
        trade_index = next((i for i, trade in enumerate(trades) if trade['id'] == selected_id), -1)
        if trade_index != -1:
            selected_trade_data = trades[trade_index]

    # --- Setup Defaults ---
    default_date = selected_trade_data.get('date', datetime.now().strftime('%Y-%m-%d'))
    default_instrument = selected_trade_data.get('instrument', INSTRUMENT_OPTIONS[0])
    default_direction = selected_trade_data.get('direction', DIRECTION_OPTIONS[0])
    default_contracts = selected_trade_data.get('contracts', 1)
    
    if is_new:
        default_commissions = DEFAULT_COMMISSION_PER_CONTRACT * default_contracts
        default_fees = DEFAULT_FEES_PER_CONTRACT * default_contracts
    else:
        default_commissions = selected_trade_data.get('commissions', 0.0)
        default_fees = selected_trade_data.get('fees', 0.0)

    default_commissions = float(default_commissions)
    default_fees = float(default_fees)
    
    instr_index = INSTRUMENT_OPTIONS.index(default_instrument) if default_instrument in INSTRUMENT_OPTIONS else 0
    dir_index = DIRECTION_OPTIONS.index(default_direction) if default_direction in DIRECTION_OPTIONS else 0

    st.markdown(f"## {'New Trade Log' if is_new else 'Edit Trade Record'}")
    st.markdown("<hr style='border-top: 1px solid #333333; margin: 10px 0 20px 0;'>", unsafe_allow_html=True)

    
    # --- Start the Form ---
    with st.form(key='trade_form', clear_on_submit=False):
        
        # --- Section 1: Core Trade Details ---
        st.markdown("### Execution Details")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            date = st.date_input("Date", value=datetime.strptime(default_date, '%Y-%m-%d'))
        with col2:
            instrument = st.selectbox("Instrument", options=INSTRUMENT_OPTIONS, index=instr_index)
        with col3:
            direction = st.selectbox("Direction", options=DIRECTION_OPTIONS, index=dir_index)
            
        col4, col5, col6 = st.columns(3)
        with col4:
            contracts = st.number_input("Contracts", min_value=1, value=default_contracts, step=1, key="contracts_input")
        with col5:
            entry = st.text_input("Entry Price", value=selected_trade_data.get('entry', ''), placeholder="e.g., 15000.25")
        with col6:
            exit = st.text_input("Exit Price", value=selected_trade_data.get('exit', ''), placeholder="e.g., 15010.75")
        
        st.markdown("<br>", unsafe_allow_html=True) # Add vertical space

        # --- Section 2: Costs and P&L ---
        st.markdown("### Transaction Costs")
        
        if is_new:
            calculated_commissions = DEFAULT_COMMISSION_PER_CONTRACT * contracts
            calculated_fees = DEFAULT_FEES_PER_CONTRACT * contracts
        else:
            calculated_commissions = default_commissions
            calculated_fees = default_fees

        col7, col8 = st.columns(2)
        with col7:
            commissions = st.number_input("Commissions ($)", min_value=0.0, value=calculated_commissions, step=0.01, format="%.2f", key="commissions_input_final")
        with col8:
            fees = st.number_input("Fees & Slippage ($)", min_value=0.0, value=calculated_fees, step=0.01, format="%.2f", key="fees_input_final")
        
        # Highlight the key cost information, using minimal styling
        st.markdown(f"""
            <div style="background-color: #1e1e1e; padding: 10px; border-left: 4px solid #3b82f6; border-radius: 4px;">
                <p style="margin: 0; font-size: 14px; color: #a1a1aa;">
                    Fixed Cost for **{contracts}** contract(s): 
                    <span style="font-weight: bold; color: #ffffff;">${(calculated_commissions + calculated_fees):.2f}</span>
                    (Total $1.90 per contract)
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # --- Section 3: Analysis ---
        st.markdown("### Post-Trade Analysis")
        setup = st.text_input("Setup/Model Used", 
                              value=selected_trade_data.get('setup', ''), placeholder="e.g., Core Trend Reversal, Supply Zone Fade")
        
        notes = st.text_area("Trade Notes & Self-Critique", 
                             value=selected_trade_data.get('notes', ''), placeholder="What was the thesis? Execution quality? What did I learn?")
        
        # --- Section 4: Image Management ---
        st.markdown("### Screenshot (Optional)")
        
        current_image_path = selected_trade_data.get('tradeImagePath')
        delete_current_image = False
        uploaded_file = None

        if current_image_path and os.path.exists(current_image_path):
            st.image(current_image_path, caption="Current Chart Screenshot", use_column_width=True)
            delete_current_image = st.checkbox("Permanently remove current screenshot", key="delete_image")
        
        uploaded_file = st.file_uploader(
            "Upload New Image (PNG/JPG)",
            type=["png", "jpg", "jpeg"],
            help="Upload a new screenshot for this trade.",
            key="new_image_upload"
        )
        
        st.markdown("<hr style='border-top: 1px solid #333333; margin: 20px 0;'>", unsafe_allow_html=True)

        # --- Submit Button ---
        # The button is styled via CSS (see main() function) to be sleek and primary blue.
        submitted = st.form_submit_button(("Save & Log Trade" if is_new else "Update Record"), use_container_width=True, type="primary")

    # --- Form Submission Logic ---
    if submitted:
        # P&L Calculation and Data Preparation (Unchanged)
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
            new_image_path = None
            
        # 2. Handle New Image Upload
        if uploaded_file is not None:
            path_temp = save_uploaded_file(uploaded_file)
            
            if path_temp:
                if not is_new and current_image_path and current_image_path != new_image_path and os.path.exists(current_image_path):
                    try:
                        os.remove(current_image_path)
                    except Exception:
                        pass 

                new_image_path = path_temp
            else:
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
            'commissions': commissions, 
            'fees': fees,               
            'pnl': pnl_calculated,      
            'setup': setup,
            'notes': notes,
            'tradeImagePath': new_image_path,
            'timestamp': datetime.now().isoformat()
        }

        # 4. Update the main trades list
        if is_new:
            st.session_state.trades.append(trade_data)
        else:
            st.session_state.trades[trade_index] = trade_data

        # 5. Save and Refresh
        save_data(st.session_state.trades)
        st.session_state.selected_trade_id = trade_data['id'] 
        st.rerun() 

    # --- Delete Button (Outside the form, visible in edit mode) ---
    if not is_new:
        st.markdown("<br>", unsafe_allow_html=True)
        # Use a secondary color to de-emphasize the destructive action
        st.button(
            "Delete This Record", 
            on_click=delete_selected_trade, 
            type="secondary",
            use_container_width=True,
            help="Permanently delete this trade log."
        )


# --- Main Application Logic ---

def main():
    """Initializes the app, loads data, and orchestrates the UI rendering."""
    
    # 1. Page Configuration
    st.set_page_config(
        page_title=PAGE_TITLE,
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 2. Custom CSS for Steve Jobs/Minimalist Look
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        /* GENERAL THEME (Deep Black/Charcoal) */
        .stApp {
            background-color: #0d0d0d; /* Very deep charcoal/black */
            color: #e0e0e0; /* Off-white text */
            font-family: 'Inter', sans-serif;
        }
        
        /* PRIMARY HEADERS & TYPOGRAPHY */
        h1, h2, h3, h4, .css-1dp54x6, .css-10trblm, [data-testid="stSidebar"] h1 {
            color: #fafafa;
            font-weight: 500;
        }

        /* SIDEBAR (Minimalist) */
        [data-testid="stSidebar"] {
            background-color: #111111; /* Slightly lighter than main body */
        }
        .stButton[kind="primary"] button {
            background-color: #3b82f6; /* Apple-esque Blue */
            border: none;
            color: white;
            font-weight: 600;
            transition: all 0.2s;
        }
        .stButton[kind="primary"] button:hover {
            background-color: #1d4ed8;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
        }

        /* INPUT FIELDS (Clean, High-Contrast) */
        .stTextInput, .stNumberInput, .stTextArea, .stSelectbox {
            background-color: #1a1a1a;
            border-radius: 6px;
        }
        .stTextInput input, .stNumberInput input, .stTextArea textarea {
            background-color: #1a1a1a;
            color: #f0f0f0;
            border: 1px solid #333333;
            transition: border-color 0.2s;
        }
        .stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
            border-color: #3b82f6;
            box-shadow: 0 0 0 1px #3b82f6;
        }
        
        /* FORM CONTAINERS (Removing Streamlit's default bulky box) */
        .stForm {
            padding: 0;
            border: none;
        }
        
        /* DELETE BUTTON (Subtle, secondary action) */
        .stButton[kind="secondary"] button {
            background-color: #1a1a1a;
            border: 1px solid #404040;
            color: #a3a3a3;
            transition: all 0.2s;
        }
        .stButton[kind="secondary"] button:hover {
            border-color: #dc2626;
            color: #dc2626;
            background-color: #1c0f0f;
        }

        /* Hiding specific Streamlit elements for clean UI */
        footer {visibility: hidden;}
        header {visibility: hidden;}

        </style>
        """, unsafe_allow_html=True)


    # 3. Initialize Session State
    if 'trades' not in st.session_state:
        st.session_state.trades = load_data()
    
    if 'selected_trade_id' not in st.session_state:
        st.session_state.selected_trade_id = None
        
    # 4. Render UI Components
    
    # Left Sidebar: Trade List
    render_trade_list(st.session_state.trades)
    
    # Main Area: Trade Form / Detail View
    render_trade_form()

# 5. Run the Main Function
if __name__ == '__main__':
    main()
