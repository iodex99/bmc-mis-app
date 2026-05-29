"""Application stylesheet — a modern, professional light theme."""

# Palette
INDIGO = "#4F46E5"
INDIGO_DARK = "#4338CA"
INDIGO_TINT = "#EEF2FF"
NAVY = "#0F172A"
NAVY_2 = "#1E293B"
SLATE_50 = "#F8FAFC"
SLATE_100 = "#F1F5F9"
SLATE_200 = "#E2E8F0"
SLATE_300 = "#CBD5E1"
SLATE_400 = "#94A3B8"
SLATE_500 = "#64748B"
SLATE_600 = "#475569"
WHITE = "#FFFFFF"


STYLESHEET = f"""
* {{
    font-family: 'Segoe UI Variable Text', 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
    color: {NAVY};
}}

QMainWindow,
#central,
#content,
QStackedWidget,
QStackedWidget > QWidget,
QScrollArea,
QScrollArea > QWidget > QWidget {{
    background: {SLATE_100};
}}
QDialog {{ background: {SLATE_50}; }}

/* ============ SIDEBAR ============ */

#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {NAVY}, stop:1 {NAVY_2});
    border: none;
}}
#brand {{
    color: {WHITE};
    font-size: 15px;
    font-weight: 700;
    padding: 26px 16px;
    background: transparent;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}}
#nav {{
    background: transparent;
    border: none;
    outline: 0;
    padding: 10px 8px;
}}
#nav::item {{
    color: {SLATE_300};
    padding: 11px 16px;
    border-radius: 8px;
    margin: 2px 4px;
    border: none;
}}
#nav::item:hover:!selected {{
    background: rgba(255, 255, 255, 0.06);
    color: {WHITE};
}}
#nav::item:selected {{
    background: {INDIGO};
    color: {WHITE};
    font-weight: 600;
}}

/* ============ PAGE TYPOGRAPHY ============ */

#pageHeading {{
    font-size: 26px;
    font-weight: 700;
    color: {NAVY};
    padding: 0;
    margin: 0;
}}
#pageNote {{
    font-size: 13px;
    color: {SLATE_500};
    margin-top: 2px;
    margin-bottom: 8px;
}}

/* ============ BUTTONS ============ */

QPushButton {{
    background: {WHITE};
    color: {NAVY};
    border: 1px solid {SLATE_300};
    padding: 8px 18px;
    border-radius: 7px;
    font-weight: 500;
    min-height: 18px;
}}
QPushButton:hover {{
    background: {SLATE_50};
    border-color: {SLATE_400};
}}
QPushButton:pressed {{ background: {SLATE_200}; }}
QPushButton:disabled {{
    color: {SLATE_400};
    background: {SLATE_100};
    border-color: {SLATE_200};
}}

QPushButton#primary {{
    background: {INDIGO};
    color: {WHITE};
    border: 1px solid {INDIGO_DARK};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {INDIGO_DARK}; border-color: {INDIGO_DARK}; }}
QPushButton#primary:pressed {{ background: #3730A3; }}
QPushButton#primary:disabled {{
    background: #A5B4FC;
    border-color: #A5B4FC;
    color: {WHITE};
}}

QPushButton#danger {{
    background: {WHITE};
    color: #B91C1C;
    border: 1px solid #FCA5A5;
}}
QPushButton#danger:hover {{ background: #FEF2F2; }}

/* ============ INPUTS ============ */

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {WHITE};
    border: 1px solid {SLATE_300};
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: {INDIGO};
    selection-color: {WHITE};
    min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border: 1px solid {INDIGO};
}}
QLineEdit:disabled, QComboBox:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled {{
    background: {SLATE_100};
    color: {SLATE_400};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid {SLATE_500};
    margin-right: 9px;
}}
QComboBox QAbstractItemView {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    selection-background-color: {INDIGO_TINT};
    selection-color: {NAVY};
    padding: 4px;
    outline: 0;
}}

/* ============ TABS ============ */

QTabWidget::pane {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    border-radius: 8px;
    top: -1px;
    padding: 6px;
}}
QTabWidget::tab-bar {{ alignment: left; }}

QTabBar {{
    background: transparent;
    qproperty-drawBase: 0;
    qproperty-expanding: false;
}}
QTabBar::tab {{
    background: {SLATE_100};
    color: {SLATE_600};
    padding: 9px 16px;
    margin-right: 3px;
    border: 1px solid {SLATE_200};
    border-bottom: none;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    min-width: 72px;
    font-weight: 500;
}}
QTabBar::tab:selected {{
    background: {WHITE};
    color: {INDIGO};
    border-color: {SLATE_200};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background: {SLATE_50};
    color: {NAVY};
}}
QTabBar::scroller {{ width: 24px; }}

/* ============ TABLES ============ */

QTableWidget, QTableView {{
    background: {WHITE};
    alternate-background-color: {SLATE_50};
    border: 1px solid {SLATE_200};
    border-radius: 6px;
    gridline-color: {SLATE_100};
    selection-background-color: {INDIGO_TINT};
    selection-color: {NAVY};
}}
QTableWidget::item, QTableView::item {{
    padding: 6px 8px;
    border: none;
}}
QTableWidget::item:selected, QTableView::item:selected {{
    background: {INDIGO_TINT};
    color: {NAVY};
}}

QHeaderView::section {{
    background: {SLATE_50};
    color: {SLATE_600};
    border: none;
    border-right: 1px solid {SLATE_200};
    border-bottom: 1px solid {SLATE_200};
    padding: 9px 10px;
    font-weight: 600;
    font-size: 12px;
}}
QHeaderView::section:hover {{ background: {SLATE_100}; }}
QHeaderView {{ background: {SLATE_50}; }}

/* ============ GROUP BOX (panels / cards) ============ */

QGroupBox {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    border-radius: 10px;
    margin-top: 16px;
    padding: 16px 14px 14px 14px;
    font-weight: 600;
    color: {SLATE_600};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 14px;
    background: {WHITE};
    color: {NAVY};
    font-weight: 600;
    font-size: 13px;
}}

/* ============ LIST WIDGETS ============ */

QListWidget {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    border-radius: 6px;
    padding: 4px;
    outline: 0;
}}
QListWidget::item {{
    padding: 7px 10px;
    border-radius: 5px;
    color: {NAVY};
}}
QListWidget::item:hover {{ background: {SLATE_50}; }}
QListWidget::item:selected {{
    background: {INDIGO_TINT};
    color: {NAVY};
}}

/* ============ CHECKBOX & RADIO ============ */

QCheckBox, QRadioButton {{
    color: {NAVY};
    spacing: 8px;
    padding: 3px 0;
}}

/* ============ SCROLLBARS ============ */

QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {SLATE_300};
    border-radius: 5px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{ background: {SLATE_400}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{
    background: {SLATE_300};
    border-radius: 5px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{ background: {SLATE_400}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    width: 0; height: 0; background: transparent;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* ============ STATUS BAR ============ */

QStatusBar {{
    background: {SLATE_50};
    color: {SLATE_500};
    border-top: 1px solid {SLATE_200};
    padding: 4px 12px;
}}

/* ============ MENUS & TOOLTIPS ============ */

QMenu {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 18px;
    border-radius: 4px;
}}
QMenu::item:selected {{ background: {INDIGO_TINT}; }}

QToolTip {{
    background: {NAVY};
    color: {SLATE_100};
    border: none;
    padding: 6px 10px;
    border-radius: 4px;
}}

/* ============ DASHBOARD METRIC CARDS ============ */

QGroupBox#metricCard {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    border-radius: 12px;
    padding: 18px 16px 14px 16px;
    margin-top: 0;
    font-weight: 600;
    color: {SLATE_500};
    font-size: 12px;
}}
QGroupBox#metricCard::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 6px;
    left: 12px;
    background: {WHITE};
    color: {SLATE_500};
    font-weight: 600;
    text-transform: uppercase;
    font-size: 11px;
}}

#metricValue {{
    font-size: 26px;
    font-weight: 700;
    color: {NAVY};
}}
#metricDetail {{
    color: {SLATE_500};
    font-size: 12px;
}}

#nextStepsCard {{
    background: {INDIGO_TINT};
    border: 1px solid #C7D2FE;
    border-radius: 10px;
    color: {NAVY};
    padding: 14px 16px;
}}

QLabel {{ background: transparent; }}

/* ============ STATUS-BAR UPDATE PILL ============ */

QPushButton#updatePill {{
    background: {INDIGO_TINT};
    color: {INDIGO_DARK};
    border: 1px solid #C7D2FE;
    border-radius: 10px;
    padding: 3px 12px;
    font-weight: 600;
    font-size: 12px;
    min-height: 16px;
}}
QPushButton#updatePill:hover {{
    background: #DDE2FB;
}}

/* ============ ROW-LEVEL ACTION BUTTONS ============ */

QPushButton#rowAction {{
    background: {INDIGO};
    color: {WHITE};
    border: 1px solid {INDIGO_DARK};
    border-radius: 6px;
    padding: 5px 14px;
    font-weight: 600;
    font-size: 12px;
    min-height: 14px;
}}
QPushButton#rowAction:hover {{
    background: {INDIGO_DARK};
    border-color: {INDIGO_DARK};
}}
QPushButton#rowActionDanger {{
    background: {WHITE};
    color: #B91C1C;
    border: 1px solid #FCA5A5;
    border-radius: 6px;
    padding: 5px 12px;
    font-weight: 600;
    font-size: 12px;
}}
QPushButton#rowActionDanger:hover {{
    background: #FEF2F2;
    border-color: #F87171;
}}

/* ============ STATUS PILLS ============ */

QLabel#statusOk {{
    background: #DCFCE7;
    color: #166534;
    border: 1px solid #BBF7D0;
    border-radius: 10px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 11px;
    qproperty-alignment: AlignCenter;
}}
QLabel#statusWarn {{
    background: #FEF3C7;
    color: #92400E;
    border: 1px solid #FDE68A;
    border-radius: 10px;
    padding: 2px 8px;
    font-weight: 600;
    font-size: 11px;
    qproperty-alignment: AlignCenter;
}}
QLabel#statusMuted {{
    background: {SLATE_100};
    color: {SLATE_500};
    border: 1px solid {SLATE_200};
    border-radius: 10px;
    padding: 2px 8px;
    font-weight: 500;
    font-size: 11px;
    qproperty-alignment: AlignCenter;
}}

/* ============ SECTION & EMPTY STATE ============ */

QLabel#sectionTitle {{
    font-size: 13px;
    font-weight: 600;
    color: {SLATE_600};
}}
QLabel#emptyState {{
    background: {WHITE};
    border: 1px dashed {SLATE_200};
    border-radius: 10px;
    padding: 36px 28px;
    color: {SLATE_500};
    font-size: 14px;
}}

/* ============ WELCOME PANEL ============ */

QFrame#welcomePanel {{
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1,
        stop:0 #EEF2FF, stop:1 #FAF5FF);
    border: 1px solid #C7D2FE;
    border-radius: 14px;
}}
QLabel#welcomeTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {NAVY};
}}
QLabel#welcomeBody {{
    font-size: 14px;
    color: {SLATE_600};
    line-height: 1.5;
}}

/* ============ METRIC + QUICK-ACTION CARDS ============ */

QFrame#metricCard {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    border-radius: 12px;
}}
QFrame#metricCard[accent="indigo"] {{ border-top: 3px solid {INDIGO}; }}
QFrame#metricCard[accent="rose"]   {{ border-top: 3px solid #F43F5E; }}
QFrame#metricCard[accent="emerald"] {{ border-top: 3px solid #10B981; }}
QFrame#metricCard[accent="amber"]  {{ border-top: 3px solid #F59E0B; }}

QLabel#cardLabel {{
    color: {SLATE_500};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.2px;
}}
QLabel#metricValue {{
    font-size: 26px;
    font-weight: 700;
    color: {NAVY};
    margin-top: 2px;
}}
QLabel#metricDetail {{
    color: {SLATE_500};
    font-size: 12px;
}}

QFrame#quickCard {{
    background: {WHITE};
    border: 1px solid {SLATE_200};
    border-radius: 12px;
}}
QFrame#quickCard:hover {{
    border-color: {INDIGO};
    background: #FAFBFF;
}}
QLabel#quickIcon {{
    font-size: 22px;
}}
QLabel#quickTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {NAVY};
}}
QLabel#quickArrow {{
    font-size: 18px;
    color: {INDIGO};
    font-weight: 700;
}}
QLabel#quickSubtitle {{
    color: {SLATE_500};
    font-size: 12px;
}}

QGroupBox#nextStepsCard {{
    background: {INDIGO_TINT};
    border: 1px solid #C7D2FE;
    border-radius: 10px;
}}

/* ============ TAB BAR (tweaks for badges) ============ */

QTabBar::tab {{ min-width: 110px; }}
"""
