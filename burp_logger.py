# -*- coding: utf-8 -*-
# Burp Suite Request/Response Logger Extension - Proxy Style
# Save this file as burp_logger_proxy_style.py

from burp import IBurpExtender, IHttpListener, ITab
# --- Imports ---
from javax.swing import (JPanel, JButton, JTable, JScrollPane, JSplitPane, 
                         JTextArea, JOptionPane, JTextField, JLabel, Box, 
                         BoxLayout, BorderFactory, SwingUtilities, ListSelectionModel, 
                         RowFilter, JDialog, JCheckBox, JTabbedPane,
                         JComponent, KeyStroke, AbstractAction, JComboBox, DefaultComboBoxModel,
                         SpinnerNumberModel, JSpinner, SwingConstants, JPopupMenu, JMenuItem)
from javax.swing.table import AbstractTableModel, TableRowSorter
from java.awt import (BorderLayout, Font, GridBagLayout, GridBagConstraints, 
                      Insets, FlowLayout, Dimension, GridLayout, Color)
from java.awt.event import MouseAdapter, ActionListener, KeyEvent
from java.io import File, BufferedWriter, FileWriter
from java.util import ArrayList
from java.net import URL
import datetime
import re
import json

# --- Configuration Storage ---
class FilterConfig:
    def __init__(self):
        # PROXY BEHAVIOR: Default to False (Show everything).
        self.in_scope_only = False 
        
        # Status Code Defaults
        self.show_2xx = True
        self.show_3xx = True
        self.show_4xx = True
        self.show_5xx = True
        
        # MIME Defaults
        self.mime_html = True
        self.mime_script = True
        self.mime_xml = True
        self.mime_json = True
        self.mime_css = True
        self.mime_image = True
        self.mime_other = True
        
        # Search / Extensions
        self.hide_extensions = "jpg,jpeg,png,gif,ico,svg,woff,woff2,mp4"
        self.search_term = ""
        self.use_regex = False
        self.case_sensitive = False
        
        # Advanced Filtering
        self.param_filter = ""
        self.header_filter = ""
        self.body_search = ""
        self.negative_filter = ""
        
        self.saved_filters = {}
        self.active_filter_name = None

# --- Main Extender ---
class BurpExtender(IBurpExtender, IHttpListener, ITab):
    
    DEFAULT_EXPORT_DIR = "/media/sf_Kali_Folder"
    MAX_LOG_ENTRIES = 5000  # PREVENT CRASH: Limit memory usage

    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        self.log_entries = []
        self.filter_config = FilterConfig()
        
        callbacks.setExtensionName("Request/Response Logger Enhanced")
        
        self.create_ui()
        callbacks.registerHttpListener(self)
        callbacks.addSuiteTab(self)
        
        print("[+] Enhanced Logger ready. (Proxy Mode: Captures all, optional Scope filter)")
    
    def create_ui(self):
        self.main_panel = self.create_main_log_panel()
    
    def create_main_log_panel(self):
        panel = JPanel(BorderLayout())
        
        # --- Toolbar ---
        toolbar = JPanel()
        toolbar.setLayout(BoxLayout(toolbar, BoxLayout.X_AXIS))
        toolbar.setBorder(BorderFactory.createEmptyBorder(5, 5, 5, 5))
        
        clear_btn = JButton("Clear Log", actionPerformed=self.clear_logs)
        dedupe_btn = JButton("Remove Duplicates", actionPerformed=self.remove_duplicates)
        delete_btn = JButton("Delete Selected", actionPerformed=self.delete_selected)
        
        self.filter_btn = JButton("Filter Settings", actionPerformed=self.open_filter_dialog)
        
        # Stats Labels
        # REMOVED: setForeground(Color(50,50,50)) to fix visibility in Dark Mode
        self.stats_lbl = JLabel(" [Export Size: 0 B]")
        self.stats_lbl.setBorder(BorderFactory.createEmptyBorder(0, 10, 0, 10))
        
        self.filter_status_lbl = JLabel(" (Showing All)")
        
        export_btn = JButton("Export Selected", actionPerformed=self.export_selected)
        export_all_btn = JButton("Export Visible", actionPerformed=self.export_all)
        
        toolbar.add(clear_btn)
        toolbar.add(Box.createHorizontalStrut(5))
        toolbar.add(dedupe_btn)
        toolbar.add(Box.createHorizontalStrut(5))
        toolbar.add(delete_btn)
        toolbar.add(Box.createHorizontalStrut(15))
        
        toolbar.add(self.filter_btn)
        toolbar.add(self.filter_status_lbl)
        toolbar.add(self.stats_lbl) 
        toolbar.add(Box.createHorizontalGlue()) 
        
        toolbar.add(export_btn)
        toolbar.add(Box.createHorizontalStrut(5))
        toolbar.add(export_all_btn)
        
        # --- Table ---
        self.table_model = LogTableModel(self.log_entries)
        self.log_table = JTable(self.table_model)
        self.sorter = TableRowSorter(self.table_model)
        self.log_table.setRowSorter(self.sorter)
        self.log_table.setSelectionMode(ListSelectionModel.MULTIPLE_INTERVAL_SELECTION)
        
        self.sorter.setRowFilter(AdvancedRowFilter(self))

        # Mouse Listener
        class TableMouseListener(MouseAdapter):
            def __init__(self, extender):
                self.extender = extender
            
            def mouseClicked(self, event):
                row = self.extender.log_table.getSelectedRow()
                if row != -1:
                    model_row = self.extender.log_table.convertRowIndexToModel(row)
                    self.extender.show_details(model_row)

            def mouseReleased(self, event):
                self.checkPopup(event)

            def mousePressed(self, event):
                self.checkPopup(event)

            def checkPopup(self, event):
                if event.isPopupTrigger():
                    row = self.extender.log_table.rowAtPoint(event.getPoint())
                    if row != -1:
                        if not self.extender.log_table.isRowSelected(row):
                            self.extender.log_table.setRowSelectionInterval(row, row)
                        self.extender.show_context_menu(event)

        self.log_table.addMouseListener(TableMouseListener(self))
        table_scroll = JScrollPane(self.log_table)
        
        self.details_area = JTextArea()
        self.details_area.setEditable(False)
        self.details_area.setFont(Font("Monospaced", Font.PLAIN, 12))
        self.details_area.setLineWrap(True)
        self.details_area.setWrapStyleWord(True)
        
        details_scroll = JScrollPane(self.details_area)
        
        split_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, table_scroll, details_scroll)
        split_pane.setDividerLocation(300)
        
        panel.add(toolbar, BorderLayout.NORTH)
        panel.add(split_pane, BorderLayout.CENTER)
        
        return panel

    def show_context_menu(self, event):
        popup = JPopupMenu()
        
        send_repeater = JMenuItem("Send to Repeater")
        send_repeater.addActionListener(lambda x: self.send_to_tool("repeater"))
        
        send_intruder = JMenuItem("Send to Intruder")
        send_intruder.addActionListener(lambda x: self.send_to_tool("intruder"))
        
        popup.add(send_repeater)
        popup.add(send_intruder)
        popup.show(event.getComponent(), event.getX(), event.getY())

    def send_to_tool(self, tool_name):
        selected_rows = self.log_table.getSelectedRows()
        if not selected_rows: return
        
        view_row = selected_rows[0]
        model_row = self.log_table.convertRowIndexToModel(view_row)
        entry = self.log_entries[model_row]
        
        # ERROR FIX: Validate Host
        if entry.host == "Unknown" or entry.host is None:
            JOptionPane.showMessageDialog(self.main_panel, "Cannot send: Invalid Host/URL (Parse Error).", "Error", JOptionPane.ERROR_MESSAGE)
            return

        host = entry.host
        port = entry.url_obj.getPort()
        if port == -1:
            port = 443 if entry.url_obj.getProtocol() == "https" else 80
            
        use_https = (entry.url_obj.getProtocol() == "https")
        
        # ERROR FIX: Reconstruct bytes from cached strings to prevent Null Pointer or "Invalid Data"
        # We manually rebuild the HTTP request using the stored headers and body
        try:
            full_req_str = entry.request_headers + "\r\n\r\n" + entry.request_body
            request_bytes = self._helpers.stringToBytes(full_req_str)
        except:
            # Fallback to original object if reconstruction fails
            request_bytes = entry.message_info.getRequest()

        if tool_name == "repeater":
            self._callbacks.sendToRepeater(host, port, use_https, request_bytes, None)
        elif tool_name == "intruder":
            self._callbacks.sendToIntruder(host, port, use_https, request_bytes)

    def open_filter_dialog(self, event):
        dialog = FilterDialog(SwingUtilities.getWindowAncestor(self.main_panel), self)
        dialog.setVisible(True)
    
    def apply_filters(self):
        self.table_model.fireTableDataChanged()
        
        active_filters = []
        if self.filter_config.in_scope_only: active_filters.append("In-Scope")
        if self.filter_config.param_filter: active_filters.append("Params")
        if self.filter_config.header_filter: active_filters.append("Headers")
        if self.filter_config.body_search: active_filters.append("Body")
        if self.filter_config.negative_filter: active_filters.append("Negative")
        
        if active_filters:
            self.filter_status_lbl.setText(" (Filtered: %s)" % ", ".join(active_filters))
        else:
            self.filter_status_lbl.setText(" (Showing All)")
        
        self.update_stats_label()

    def update_stats_label(self):
        # Calculate size of VISIBLE logs only
        total_bytes = 0
        row_count = self.log_table.getRowCount()
        
        # The export separator size (two newlines + 80 chars + two newlines)
        # "\n\n" + ("=" * 80) + "\n\n"
        separator_size = 84 
        
        for view_row_idx in range(row_count):
            model_row_idx = self.log_table.convertRowIndexToModel(view_row_idx)
            entry = self.log_entries[model_row_idx]
            # Add content size + separator size to simulate export file size
            total_bytes += len(entry.get_full_details()) + separator_size
        
        if total_bytes < 1024:
            size_str = "%d B" % total_bytes
        elif total_bytes < 1048576: # 1024*1024
            size_str = "%.2f KB" % (total_bytes / 1024.0)
        else:
            size_str = "%.2f MB" % (total_bytes / 1048576.0)
            
        self.stats_lbl.setText(" [Export Size: %s]" % size_str)

    def processHttpMessage(self, toolFlag, messageIsRequest, messageInfo):
        if not messageIsRequest:
            msg_copy = self._callbacks.saveBuffersToTempFiles(messageInfo)
            pre_calculated_entry = LogEntry(msg_copy, self._helpers, 0, self._callbacks)
            
            def update_ui():
                try:
                    if len(self.log_entries) >= self.MAX_LOG_ENTRIES:
                        del self.log_entries[0] 
                    
                    pre_calculated_entry.entry_id = len(self.log_entries) + 1
                    self.log_entries.append(pre_calculated_entry)
                    
                    row_index = len(self.log_entries) - 1
                    self.table_model.fireTableRowsInserted(row_index, row_index)
                    self.update_stats_label()
                except Exception as e:
                    print("[-] Error logging request: " + str(e))
            
            SwingUtilities.invokeLater(update_ui)
            
    def show_details(self, row):
        if 0 <= row < len(self.log_entries):
            entry = self.log_entries[row]
            self.details_area.setText(entry.get_full_details())
            self.details_area.setCaretPosition(0)
            
    def clear_logs(self, event):
        self.log_entries[:] = [] 
        self.table_model.fireTableDataChanged()
        self.details_area.setText("")
        self.update_stats_label()

    def remove_duplicates(self, event):
        if not self.log_entries: return
        seen = set()
        unique = []
        for i in range(len(self.log_entries) - 1, -1, -1):
            entry = self.log_entries[i]
            sig = (entry.method, entry.url, entry.request_body, entry.status_code, entry.response_body)
            if sig not in seen:
                seen.add(sig)
                unique.insert(0, entry)
        removed = len(self.log_entries) - len(unique)
        self.log_entries[:] = unique
        self.table_model.fireTableDataChanged()
        self.update_stats_label()
        JOptionPane.showMessageDialog(self.main_panel, "Removed %d duplicate(s)." % removed)
    
    def delete_selected(self, event):
        selected_rows = self.log_table.getSelectedRows()
        if not selected_rows or len(selected_rows) == 0:
            JOptionPane.showMessageDialog(self.main_panel, "No entries selected.")
            return
        model_rows = []
        for row in selected_rows:
            model_rows.append(self.log_table.convertRowIndexToModel(row))
        model_rows.sort(reverse=True)
        for row in model_rows:
            if 0 <= row < len(self.log_entries): del self.log_entries[row]
        self.table_model.fireTableDataChanged()
        self.details_area.setText("")
        self.update_stats_label()
    
    def export_selected(self, event):
        selected_rows = self.log_table.getSelectedRows()
        if not selected_rows or len(selected_rows) == 0:
            JOptionPane.showMessageDialog(self.main_panel, "No entries selected.")
            return
        model_rows = []
        for row in selected_rows:
            model_rows.append(self.log_table.convertRowIndexToModel(row))
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = "%s/burp_export_%s.txt" % (self.DEFAULT_EXPORT_DIR, timestamp)
        try:
            file_obj = File(filepath)
            writer = BufferedWriter(FileWriter(file_obj))
            for row_idx in model_rows:
                if 0 <= row_idx < len(self.log_entries):
                    entry = self.log_entries[row_idx]
                    writer.write(entry.get_full_details())
                    writer.write("\n\n" + ("=" * 80) + "\n\n")
            writer.close()
            JOptionPane.showMessageDialog(self.main_panel, "Exported %d entry(ies) to:\n%s" % (len(model_rows), filepath))
        except Exception as e:
            JOptionPane.showMessageDialog(self.main_panel, "Export failed: %s" % str(e), "Error", JOptionPane.ERROR_MESSAGE)

    def export_all(self, event):
        row_count = self.log_table.getRowCount()
        if row_count == 0:
            JOptionPane.showMessageDialog(self.main_panel, "No filtered entries visible to export.")
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = "%s/burp_export_filtered_%s.txt" % (self.DEFAULT_EXPORT_DIR, timestamp)
        try:
            file_obj = File(filepath)
            writer = BufferedWriter(FileWriter(file_obj))
            for view_row_idx in range(row_count):
                model_row_idx = self.log_table.convertRowIndexToModel(view_row_idx)
                entry = self.log_entries[model_row_idx]
                writer.write(entry.get_full_details())
                writer.write("\n\n" + ("=" * 80) + "\n\n")
            
            writer.close()
            JOptionPane.showMessageDialog(self.main_panel, "Exported %d filtered entry(ies) to:\n%s" % (row_count, filepath))
        except Exception as e:
            JOptionPane.showMessageDialog(self.main_panel, "Export failed: %s" % str(e), "Error", JOptionPane.ERROR_MESSAGE)

    def getTabCaption(self): return "Enhanced Logger"
    def getUiComponent(self): return self.main_panel

# --- Filter Dialog ---
class FilterDialog(JDialog):
    def __init__(self, parent, extender):
        super(FilterDialog, self).__init__(parent, "Filter Settings", True)
        self.extender = extender
        self.config = extender.filter_config
        self.setLayout(BorderLayout())
        filter_panel = self.create_combined_filters_panel()
        scroll = JScrollPane(filter_panel)
        self.add(scroll, BorderLayout.CENTER)
        
        btn_panel = JPanel(FlowLayout(FlowLayout.RIGHT))
        btn_cancel = JButton("Cancel", actionPerformed=lambda e: self.dispose())
        btn_reset = JButton("Reset All", actionPerformed=self.reset_filters)
        btn_apply = JButton("Apply", actionPerformed=self.apply_action)
        btn_panel.add(btn_reset)
        btn_panel.add(btn_cancel)
        btn_panel.add(btn_apply)
        self.add(btn_panel, BorderLayout.SOUTH)
        self.setSize(750, 650)
        self.setLocationRelativeTo(parent)
    
    def create_combined_filters_panel(self):
        panel = JPanel()
        panel.setLayout(BoxLayout(panel, BoxLayout.Y_AXIS))
        panel.setBorder(BorderFactory.createEmptyBorder(10, 10, 10, 10))
        
        pnl_scope = self._create_titled_panel("Scope")
        pnl_scope.setLayout(BoxLayout(pnl_scope, BoxLayout.Y_AXIS))
        self.chk_scope = JCheckBox("Show In-Scope Only", self.config.in_scope_only)
        pnl_scope.add(self.chk_scope)
        panel.add(pnl_scope)
        panel.add(Box.createVerticalStrut(10))
        
        pnl_status = self._create_titled_panel("Status Codes")
        pnl_status.setLayout(GridLayout(2, 2, 5, 5))
        self.chk_2xx = JCheckBox("2xx (Success)", self.config.show_2xx)
        self.chk_3xx = JCheckBox("3xx (Redirect)", self.config.show_3xx)
        self.chk_4xx = JCheckBox("4xx (Client Error)", self.config.show_4xx)
        self.chk_5xx = JCheckBox("5xx (Server Error)", self.config.show_5xx)
        pnl_status.add(self.chk_2xx); pnl_status.add(self.chk_3xx)
        pnl_status.add(self.chk_4xx); pnl_status.add(self.chk_5xx)
        panel.add(pnl_status)
        panel.add(Box.createVerticalStrut(10))
        
        pnl_mime = self._create_titled_panel("Content Types (MIME)")
        pnl_mime.setLayout(GridLayout(3, 3, 5, 5))
        self.chk_html = JCheckBox("HTML", self.config.mime_html)
        self.chk_script = JCheckBox("Script", self.config.mime_script)
        self.chk_xml = JCheckBox("XML", self.config.mime_xml)
        self.chk_json = JCheckBox("JSON", self.config.mime_json)
        self.chk_css = JCheckBox("CSS", self.config.mime_css)
        self.chk_image = JCheckBox("Images", self.config.mime_image)
        self.chk_other = JCheckBox("Other", self.config.mime_other)
        pnl_mime.add(self.chk_html); pnl_mime.add(self.chk_script); pnl_mime.add(self.chk_xml)
        pnl_mime.add(self.chk_json); pnl_mime.add(self.chk_css); pnl_mime.add(self.chk_image)
        pnl_mime.add(self.chk_other)
        panel.add(pnl_mime)
        panel.add(Box.createVerticalStrut(10))
        
        pnl_search = self._create_titled_panel("Text Search")
        pnl_search.setLayout(GridBagLayout())
        gbc = GridBagConstraints()
        gbc.fill = GridBagConstraints.HORIZONTAL
        gbc.insets = Insets(5, 5, 5, 5)
        gbc.weightx = 1.0
        gbc.gridx = 0; gbc.gridy = 0; gbc.gridwidth = 2
        pnl_search.add(JLabel("URL/Method search:"), gbc)
        gbc.gridy = 1
        self.txt_search = JTextField(self.config.search_term, 30)
        pnl_search.add(self.txt_search, gbc)
        gbc.gridy = 2; gbc.gridwidth = 1
        self.chk_regex = JCheckBox("Use Regex", self.config.use_regex)
        pnl_search.add(self.chk_regex, gbc)
        gbc.gridx = 1
        self.chk_case = JCheckBox("Case Sensitive", self.config.case_sensitive)
        pnl_search.add(self.chk_case, gbc)
        panel.add(pnl_search)
        panel.add(Box.createVerticalStrut(10))
        
        pnl_advanced = self._create_titled_panel("Advanced Filters")
        pnl_advanced.setLayout(GridBagLayout())
        agbc = GridBagConstraints()
        agbc.fill = GridBagConstraints.HORIZONTAL
        agbc.insets = Insets(3, 5, 3, 5)
        agbc.weightx = 1.0
        agbc.gridx = 0; agbc.gridy = 0
        pnl_advanced.add(JLabel("URL Parameter:"), agbc)
        agbc.gridy = 1
        self.txt_param_filter = JTextField(self.config.param_filter)
        pnl_advanced.add(self.txt_param_filter, agbc)
        agbc.gridy = 2
        pnl_advanced.add(JLabel("Header (request/response):"), agbc)
        agbc.gridy = 3
        self.txt_header_filter = JTextField(self.config.header_filter)
        pnl_advanced.add(self.txt_header_filter, agbc)
        agbc.gridy = 4
        pnl_advanced.add(JLabel("Body Content:"), agbc)
        agbc.gridy = 5
        self.txt_body_search = JTextField(self.config.body_search)
        pnl_advanced.add(self.txt_body_search, agbc)
        agbc.gridy = 6
        pnl_advanced.add(JLabel("Negative Filter (exclude):"), agbc)
        agbc.gridy = 7
        self.txt_negative_filter = JTextField(self.config.negative_filter)
        pnl_advanced.add(self.txt_negative_filter, agbc)
        panel.add(pnl_advanced)
        panel.add(Box.createVerticalStrut(10))
        
        pnl_ext = self._create_titled_panel("Hide File Extensions")
        pnl_ext.setLayout(BorderLayout(5, 5))
        pnl_ext.add(JLabel("Comma-separated (e.g., jpg,png,css,js):"), BorderLayout.NORTH)
        self.txt_ext = JTextField(self.config.hide_extensions)
        pnl_ext.add(self.txt_ext, BorderLayout.CENTER)
        panel.add(pnl_ext)
        return panel
    
    def _create_titled_panel(self, title):
        p = JPanel()
        p.setBorder(BorderFactory.createTitledBorder(title))
        return p
    
    def reset_filters(self, event):
        self.chk_scope.setSelected(False)
        self.chk_2xx.setSelected(True); self.chk_3xx.setSelected(True)
        self.chk_4xx.setSelected(True); self.chk_5xx.setSelected(True)
        self.chk_html.setSelected(True); self.chk_script.setSelected(True)
        self.chk_xml.setSelected(True); self.chk_json.setSelected(True)
        self.chk_css.setSelected(True); self.chk_image.setSelected(True)
        self.chk_other.setSelected(True)
        self.txt_search.setText(""); self.chk_regex.setSelected(False)
        self.chk_case.setSelected(False)
        self.txt_param_filter.setText(""); self.txt_header_filter.setText("")
        self.txt_body_search.setText(""); self.txt_negative_filter.setText("")
        self.txt_ext.setText("jpg,jpeg,png,gif,ico,svg,woff,woff2,mp4")

    def apply_action(self, event):
        c = self.config
        c.in_scope_only = self.chk_scope.isSelected()
        c.show_2xx = self.chk_2xx.isSelected(); c.show_3xx = self.chk_3xx.isSelected()
        c.show_4xx = self.chk_4xx.isSelected(); c.show_5xx = self.chk_5xx.isSelected()
        c.mime_html = self.chk_html.isSelected(); c.mime_script = self.chk_script.isSelected()
        c.mime_xml = self.chk_xml.isSelected(); c.mime_json = self.chk_json.isSelected()
        c.mime_css = self.chk_css.isSelected(); c.mime_image = self.chk_image.isSelected()
        c.mime_other = self.chk_other.isSelected()
        c.search_term = self.txt_search.getText()
        c.use_regex = self.chk_regex.isSelected()
        c.case_sensitive = self.chk_case.isSelected()
        c.hide_extensions = self.txt_ext.getText()
        c.param_filter = self.txt_param_filter.getText()
        c.header_filter = self.txt_header_filter.getText()
        c.body_search = self.txt_body_search.getText()
        c.negative_filter = self.txt_negative_filter.getText()
        self.extender.apply_filters()
        self.dispose()

# --- Advanced Row Filter ---
class AdvancedRowFilter(RowFilter):
    def __init__(self, extender):
        self.extender = extender
    
    def include(self, entry):
        row_idx = entry.getIdentifier()
        if row_idx >= len(self.extender.log_entries): return False
        
        log = self.extender.log_entries[row_idx]
        conf = self.extender.filter_config
        
        if conf.in_scope_only:
            if not log.url_obj or not self.extender._callbacks.isInScope(log.url_obj):
                return False
        
        s = log.status_code
        if 200 <= s < 300 and not conf.show_2xx: return False
        if 300 <= s < 400 and not conf.show_3xx: return False
        if 400 <= s < 500 and not conf.show_4xx: return False
        if 500 <= s < 600 and not conf.show_5xx: return False
        
        m = log.mime_type
        if m == "HTML" and not conf.mime_html: return False
        if m == "script" and not conf.mime_script: return False
        if m == "XML" and not conf.mime_xml: return False
        if m == "JSON" and not conf.mime_json: return False
        if m == "CSS" and not conf.mime_css: return False
        if (m == "JPEG" or m == "GIF" or m == "PNG" or m == "image") and not conf.mime_image: return False
        
        known = ["HTML", "script", "XML", "JSON", "CSS", "JPEG", "GIF", "PNG", "image"]
        if m not in known and not conf.mime_other: return False
        
        if conf.hide_extensions:
            exts = [x.strip().lower() for x in conf.hide_extensions.split(',')]
            if log.extension.lower() in exts: return False
        
        if conf.search_term:
            term = conf.search_term
            haystack = "%s %s %s" % (log.url, log.method, str(log.status_code))
            if not conf.use_regex:
                if not conf.case_sensitive:
                    term = term.lower(); haystack = haystack.lower()
                if term not in haystack: return False
            else:
                flags = 0 if conf.case_sensitive else re.IGNORECASE
                try:
                    if not re.search(term, haystack, flags): return False
                except: pass
        
        if conf.param_filter:
            param_filter = conf.param_filter.strip()
            if param_filter and '?' in log.url:
                query_string = log.url.split('?', 1)[1]
                if '#' in query_string: query_string = query_string.split('#')[0]
                found = False
                for param_pair in query_string.split('&'):
                    if param_filter.lower() in param_pair.lower():
                        found = True; break
                if not found: return False
            elif param_filter: return False
        
        if conf.header_filter:
            header_filter = conf.header_filter.strip().lower()
            if header_filter:
                found = (header_filter in log.request_headers.lower())
                if not found and log.response_headers:
                    found = (header_filter in log.response_headers.lower())
                if not found: return False
        
        if conf.body_search:
            body_search = conf.body_search.strip().lower()
            if body_search:
                found = (log.request_body and body_search in log.request_body.lower())
                if not found and log.response_body:
                    found = (body_search in log.response_body.lower())
                if not found: return False
        
        if conf.negative_filter:
            negative_filter = conf.negative_filter.strip().lower()
            if negative_filter:
                patterns = [p.strip() for p in negative_filter.split('|')]
                for pattern in patterns:
                    if pattern and pattern in log.url.lower(): return False
        return True

# --- Data Structures ---
class LogTableModel(AbstractTableModel):
    def __init__(self, log_entries):
        self.log_entries = log_entries
        self.column_names = ["#", "Time", "Host", "Method", "URL", "Status", "MIME", "Ext"]
    def getRowCount(self): return len(self.log_entries)
    def getColumnCount(self): return len(self.column_names)
    def getColumnName(self, column): return self.column_names[column]
    def getValueAt(self, row, column):
        if row >= len(self.log_entries): return ""
        entry = self.log_entries[row]
        if column == 0: return entry.entry_id
        elif column == 1: return entry.timestamp
        elif column == 2: return entry.host
        elif column == 3: return entry.method
        elif column == 4: return entry.url
        elif column == 5: return entry.status_code
        elif column == 6: return entry.mime_type
        elif column == 7: return entry.extension
        return ""

class LogEntry:
    def __init__(self, message_info, helpers, entry_id, callbacks):
        self.entry_id = entry_id
        self.timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.message_info = message_info
        self.helpers = helpers
        
        self.url_obj = message_info.getUrl()
        
        if self.url_obj:
            self.url = str(self.url_obj)
            self.host = self.url_obj.getHost()
            path = self.url_obj.getPath()
            self.extension = path.split('.')[-1] if '.' in path else ""
        else:
            self.url = "Unknown"; self.host = "Unknown"; self.extension = ""

        req_info = helpers.analyzeRequest(message_info)
        self.method = req_info.getMethod()
        
        req_bytes = message_info.getRequest()
        req_offset = req_info.getBodyOffset()
        
        self.request_headers = helpers.bytesToString(req_bytes[:req_offset]).strip()
        self.request_body = helpers.bytesToString(req_bytes[req_offset:])
        
        if message_info.getResponse():
            res_info = helpers.analyzeResponse(message_info.getResponse())
            self.status_code = res_info.getStatusCode()
            self.mime_type = res_info.getStatedMimeType()
            
            resp_bytes = message_info.getResponse()
            resp_offset = res_info.getBodyOffset()
            
            self.response_headers = helpers.bytesToString(resp_bytes[:resp_offset]).strip()
            self.response_body = helpers.bytesToString(resp_bytes[resp_offset:])
        else:
            self.status_code = 0
            self.mime_type = "Unknown"
            self.response_headers = ""
            self.response_body = ""
    
    def get_full_details(self):
        lines = ["ENTRY #%d | %s | %s" % (self.entry_id, self.method, self.url)]
        lines.append("-" * 60)
        lines.append(self.request_headers)
        lines.append("")
        lines.append(self.request_body)
        
        if self.response_headers:
            lines.append("\n" + "-" * 60 + "\nRESPONSE\n" + "-" * 60)
            lines.append(self.response_headers)
            lines.append("")
            lines.append(self.response_body)
        return '\n'.join(lines)
