#!/usr/bin/env python3
"""
Contexts Tab Module
Extracted from redesigned_comprehensive_gui.py
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv


class ContextsTab:
    """New Contexts screen with full CRUD operations"""

    def __init__(self, parent, db_manager):
        self.parent = parent
        self.db_manager = db_manager
        self.frame = ttk.Frame(parent)

    def create_widgets(self):
        """Create contexts management interface"""
        # Title
        title_label = ttk.Label(
            self.frame,
            text="📄 Contexts Management",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(10, 20))

        # Control buttons
        self.create_context_buttons()

        # Contexts grid
        self.create_contexts_grid()

        return self.frame

    def create_context_buttons(self):
        """Create context management buttons"""
        button_frame = ttk.Frame(self.frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1 - Main operations
        row1 = ttk.Frame(button_frame)
        row1.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(row1, text="👁️ View Context", command=self.view_context).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="✏️ Edit Context", command=self.edit_context).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🗑️ Delete Selected", command=self.delete_contexts).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(row1, text="🔄 Refresh", command=self.refresh_contexts).pack(side=tk.RIGHT)

        # Row 2 - Export and search
        row2 = ttk.Frame(button_frame)
        row2.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(row2, text="📊 Export CSV", command=self.export_contexts_csv).pack(side=tk.LEFT, padx=(0, 5))

        # Search frame
        search_frame = ttk.Frame(button_frame)
        search_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(search_frame, text="Search/Filter:").pack(side=tk.LEFT)
        self.context_search_var = tk.StringVar()
        self.context_search_var.trace("w", self.filter_contexts)
        search_entry = ttk.Entry(search_frame, textvariable=self.context_search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=(5, 10))

    def create_contexts_grid(self):
        """Create contexts grid"""
        # Grid frame
        grid_frame = ttk.Frame(self.frame)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Contexts tree
        columns = ('timestamp', 'project_session', 'agent_id', 'context_snippet')
        self.contexts_tree = ttk.Treeview(
            grid_frame,
            columns=columns,
            show='tree headings',
            selectmode='extended'
        )

        # Configure columns
        self.contexts_tree.heading('#0', text='ID')
        self.contexts_tree.heading('timestamp', text='Timestamp')
        self.contexts_tree.heading('project_session', text='Project → Session')
        self.contexts_tree.heading('agent_id', text='Agent ID')
        self.contexts_tree.heading('context_snippet', text='Context (first 100 chars)')

        # Set column widths
        self.contexts_tree.column('#0', width=50)
        self.contexts_tree.column('timestamp', width=150)
        self.contexts_tree.column('project_session', width=200)
        self.contexts_tree.column('agent_id', width=120)
        self.contexts_tree.column('context_snippet', width=300)

        # Make columns sortable
        for col in columns:
            self.contexts_tree.heading(col, command=lambda c=col: self.sort_contexts_column(c))

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=self.contexts_tree.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL, command=self.contexts_tree.xview)
        self.contexts_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack grid and scrollbars
        self.contexts_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        # Configure grid weights
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)

        # Load initial data
        self.refresh_contexts()

    def refresh_contexts(self):
        """Refresh contexts display"""
        # Clear existing items
        for item in self.contexts_tree.get_children():
            self.contexts_tree.delete(item)

        try:
            contexts = self.db_manager.execute_query('''
                SELECT context_id, timestamp, project, session, agent_id, context
                FROM contexts
                ORDER BY timestamp DESC
            ''')

            for context in contexts:
                context_id, timestamp, project, session, agent_id, full_context = context

                # Create snippet
                context_snippet = full_context[:100] + "..." if len(full_context) > 100 else full_context
                project_session = f"{project or 'Unknown'} → {session or 'Unknown'}"

                self.contexts_tree.insert(
                    '',
                    'end',
                    text=str(context_id),
                    values=(timestamp, project_session, agent_id, context_snippet)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load contexts: {e}")

    def view_context(self):
        """View full context in popup"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a context to view")
            return

        context_id = self.contexts_tree.item(selection[0])['text']
        try:
            result = self.db_manager.execute_query(
                "SELECT context, agent_id, timestamp FROM contexts WHERE context_id = ?",
                (context_id,)
            )

            if result:
                context, agent_id, timestamp = result[0]
                ViewContextDialog(self.frame, context_id, context, agent_id, timestamp)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load context: {e}")

    def edit_context(self):
        """Edit context in popup"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a context to edit")
            return

        context_id = self.contexts_tree.item(selection[0])['text']
        try:
            result = self.db_manager.execute_query(
                "SELECT context, agent_id, timestamp FROM contexts WHERE context_id = ?",
                (context_id,)
            )

            if result:
                context, agent_id, timestamp = result[0]
                dialog = EditContextDialog(self.frame, context_id, context, agent_id, timestamp)
                new_context = dialog.show()

                if new_context:
                    self.db_manager.execute_update(
                        "UPDATE contexts SET context = ? WHERE context_id = ?",
                        (new_context, context_id)
                    )
                    self.refresh_contexts()
                    messagebox.showinfo("Success", "Context updated successfully")
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to edit context: {e}")

    def delete_contexts(self):
        """Delete selected contexts with confirmation"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select contexts to delete")
            return

        context_ids = [self.contexts_tree.item(item)['text'] for item in selection]
        count = len(context_ids)

        if messagebox.askyesno("Confirm Deletion", f"Delete {count} context(s)?"):
            try:
                for context_id in context_ids:
                    self.db_manager.execute_update(
                        "DELETE FROM contexts WHERE context_id = ?", (context_id,)
                    )

                self.refresh_contexts()
                messagebox.showinfo("Success", f"Deleted {count} context(s)")
            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to delete contexts: {e}")

    def export_contexts_csv(self):
        """Export contexts to CSV"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )

        if filename:
            try:
                contexts = self.db_manager.execute_query('''
                    SELECT context_id, timestamp, project, session, agent_id, context
                    FROM contexts
                    ORDER BY timestamp DESC
                ''')

                with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.writer(csvfile)
                    writer.writerow(['Context ID', 'Timestamp', 'Project', 'Session', 'Agent ID', 'Context'])

                    for context in contexts:
                        writer.writerow(context)

                messagebox.showinfo("Success", f"Exported {len(contexts)} contexts to {filename}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Failed to export: {e}")

    def filter_contexts(self, *args):
        """Filter contexts based on search text"""
        search_text = self.context_search_var.get().lower()

        # Clear and repopulate with filtered results
        for item in self.contexts_tree.get_children():
            self.contexts_tree.delete(item)

        try:
            contexts = self.db_manager.execute_query('''
                SELECT context_id, timestamp, project, session, agent_id, context
                FROM contexts
                WHERE LOWER(agent_id) LIKE ? OR LOWER(context) LIKE ?
                ORDER BY timestamp DESC
            ''', (f'%{search_text}%', f'%{search_text}%'))

            for context in contexts:
                context_id, timestamp, project, session, agent_id, full_context = context

                # Create snippet
                context_snippet = full_context[:100] + "..." if len(full_context) > 100 else full_context
                project_session = f"{project or 'Unknown'} → {session or 'Unknown'}"

                self.contexts_tree.insert(
                    '',
                    'end',
                    text=str(context_id),
                    values=(timestamp, project_session, agent_id, context_snippet)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to filter contexts: {e}")

    def sort_contexts_column(self, column):
        """Sort contexts by column"""
        # Get current items from tree
        items = [(self.contexts_tree.set(child, column), child) for child in self.contexts_tree.get_children('')]

        # Sort items (special handling for numeric context_id and dates)
        if column == 'context_id':
            items.sort(key=lambda x: int(x[0]) if x[0].isdigit() else 0, reverse=getattr(self, f'_reverse_context_{column}', False))
        elif column == 'timestamp':
            items.sort(key=lambda x: x[0], reverse=getattr(self, f'_reverse_context_{column}', False))
        else:
            items.sort(reverse=getattr(self, f'_reverse_context_{column}', False))

        # Rearrange items in sorted order
        for index, (val, child) in enumerate(items):
            self.contexts_tree.move(child, '', index)

        # Toggle sort direction for next click
        setattr(self, f'_reverse_context_{column}', not getattr(self, f'_reverse_context_{column}', False))


# Dialog classes
class ViewContextDialog:
    """Dialog for viewing full context"""

    def __init__(self, parent, context_id, context, agent_id, timestamp):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"View Context {context_id}")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)

        # Info frame
        info_frame = ttk.Frame(self.dialog)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Context ID: {context_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Agent ID: {agent_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Timestamp: {timestamp}").pack(anchor=tk.W)

        # Context display
        text_frame = ttk.Frame(self.dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD, state=tk.DISABLED)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Insert context
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.insert('1.0', context)
        self.text_widget.config(state=tk.DISABLED)

        # Close button
        ttk.Button(self.dialog, text="Close", command=self.dialog.destroy).pack(pady=10)


class EditContextDialog:
    """Dialog for editing context"""

    def __init__(self, parent, context_id, context, agent_id, timestamp):
        self.parent = parent
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(f"Edit Context {context_id}")
        self.dialog.geometry("800x600")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # Info frame
        info_frame = ttk.Frame(self.dialog)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Context ID: {context_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Agent ID: {agent_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Timestamp: {timestamp}").pack(anchor=tk.W)

        # Context editor
        text_frame = ttk.Frame(self.dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Insert context
        self.text_widget.insert('1.0', context)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save", command=self.on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

    def show(self):
        """Show dialog and return result"""
        self.parent.wait_window(self.dialog)
        return self.result

    def on_save(self):
        """Handle save button"""
        self.result = self.text_widget.get('1.0', tk.END).strip()
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()