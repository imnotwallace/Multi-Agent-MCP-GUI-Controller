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
        ttk.Button(row1, text="🧩 View Chunks", command=self.view_chunks).pack(side=tk.LEFT, padx=(0, 5))
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
        columns = ('timestamp', 'project_session', 'agent_id', 'chunk_count', 'context_summary')
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
        self.contexts_tree.heading('chunk_count', text='No. of Chunks')
        self.contexts_tree.heading('context_summary', text='Context Summary')

        # Set column widths
        self.contexts_tree.column('#0', width=50)
        self.contexts_tree.column('timestamp', width=150)
        self.contexts_tree.column('project_session', width=200)
        self.contexts_tree.column('agent_id', width=120)
        self.contexts_tree.column('chunk_count', width=80)
        self.contexts_tree.column('context_summary', width=300)

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
                SELECT c.id, c.created_at, p.name as project_name, s.name as session_name, c.agent_id,
                       (SELECT COUNT(*) FROM context_chunks cc WHERE cc.context_id = c.id) as chunk_count,
                       (SELECT substr(cc.chunk_content, 1, 100) FROM context_chunks cc
                        WHERE cc.context_id = c.id ORDER BY cc.chunk_index LIMIT 1) as context_summary
                FROM contexts c
                LEFT JOIN projects p ON c.project_id = p.id
                LEFT JOIN sessions s ON c.session_id = s.id
                ORDER BY c.created_at DESC
            ''')

            for context in contexts:
                context_id, timestamp, project_name, session_name, agent_id, chunk_count, context_summary = context

                # Format display values
                project_session = f"{project_name or 'Unknown'} → {session_name or 'Unknown'}"
                summary = (context_summary or "")[:100] + ("..." if context_summary and len(context_summary) > 100 else "")

                self.contexts_tree.insert(
                    '',
                    'end',
                    text=str(context_id),
                    values=(timestamp, project_session, agent_id, chunk_count or 0, summary)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load contexts: {e}")

    def view_context(self):
        """View full context (all chunks combined) in popup"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a context to view")
            return

        context_id = self.contexts_tree.item(selection[0])['text']
        try:
            # Get context metadata
            result = self.db_manager.execute_query(
                "SELECT agent_id, created_at FROM contexts WHERE id = ?",
                (context_id,)
            )

            if result:
                agent_id, timestamp = result[0]

                # Get all chunks for this context
                chunks = self.db_manager.execute_query('''
                    SELECT chunk_content FROM context_chunks
                    WHERE context_id = ?
                    ORDER BY chunk_index
                ''', (context_id,))

                # Combine all chunks
                full_context = '\n'.join([chunk[0] for chunk in chunks])

                ViewContextDialog(self.frame, context_id, full_context, agent_id, timestamp)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load context: {e}")

    def view_chunks(self):
        """View chunks for selected context in new window"""
        selection = self.contexts_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a context to view chunks")
            return

        context_id = self.contexts_tree.item(selection[0])['text']
        try:
            # Get context metadata
            result = self.db_manager.execute_query(
                "SELECT agent_id, created_at FROM contexts WHERE id = ?",
                (context_id,)
            )

            if result:
                agent_id, timestamp = result[0]
                ViewChunksWindow(self.frame, context_id, agent_id, timestamp, self.db_manager)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load context chunks: {e}")

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
                    # Delete chunks first due to foreign key constraint
                    self.db_manager.execute_update(
                        "DELETE FROM context_chunks WHERE context_id = ?", (context_id,)
                    )
                    # Delete the context metadata
                    self.db_manager.execute_update(
                        "DELETE FROM contexts WHERE id = ?", (context_id,)
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
                SELECT c.id, c.created_at, p.name as project_name, s.name as session_name, c.agent_id,
                       (SELECT COUNT(*) FROM context_chunks cc WHERE cc.context_id = c.id) as chunk_count,
                       (SELECT substr(cc.chunk_content, 1, 100) FROM context_chunks cc
                        WHERE cc.context_id = c.id ORDER BY cc.chunk_index LIMIT 1) as context_summary
                FROM contexts c
                LEFT JOIN projects p ON c.project_id = p.id
                LEFT JOIN sessions s ON c.session_id = s.id
                WHERE LOWER(c.agent_id) LIKE ? OR
                      EXISTS (SELECT 1 FROM context_chunks cc WHERE cc.context_id = c.id AND LOWER(cc.chunk_content) LIKE ?)
                ORDER BY c.created_at DESC
            ''', (f'%{search_text}%', f'%{search_text}%'))

            for context in contexts:
                context_id, timestamp, project_name, session_name, agent_id, chunk_count, context_summary = context

                # Format display values
                project_session = f"{project_name or 'Unknown'} → {session_name or 'Unknown'}"
                summary = (context_summary or "")[:100] + ("..." if context_summary and len(context_summary) > 100 else "")

                self.contexts_tree.insert(
                    '',
                    'end',
                    text=str(context_id),
                    values=(timestamp, project_session, agent_id, chunk_count or 0, summary)
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


class ViewChunksWindow:
    """Window for viewing and managing chunks for a specific context"""

    def __init__(self, parent, context_id, agent_id, timestamp, db_manager):
        self.parent = parent
        self.context_id = context_id
        self.agent_id = agent_id
        self.timestamp = timestamp
        self.db_manager = db_manager

        self.window = tk.Toplevel(parent)
        self.window.title(f"View Chunks - Context {context_id}")
        self.window.geometry("1000x700")
        self.window.transient(parent)

        self.create_widgets()
        self.refresh_chunks()

    def create_widgets(self):
        """Create widgets for chunks window"""
        # Info frame
        info_frame = ttk.Frame(self.window)
        info_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(info_frame, text=f"Context ID: {self.context_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Agent ID: {self.agent_id}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Timestamp: {self.timestamp}").pack(anchor=tk.W)

        # Buttons frame
        button_frame = ttk.Frame(self.window)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(button_frame, text="➕ Add Chunk", command=self.add_chunk).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="✏️ Edit Chunk", command=self.edit_chunk).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🗑️ Delete Chunk", command=self.delete_chunk).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(button_frame, text="🔄 Refresh", command=self.refresh_chunks).pack(side=tk.RIGHT)

        # Chunks grid
        grid_frame = ttk.Frame(self.window)
        grid_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        # Chunks tree
        columns = ('chunk_index', 'content_preview', 'character_count', 'created_at')
        self.chunks_tree = ttk.Treeview(
            grid_frame,
            columns=columns,
            show='tree headings',
            selectmode='extended'
        )

        # Configure columns
        self.chunks_tree.heading('#0', text='ID')
        self.chunks_tree.heading('chunk_index', text='Index')
        self.chunks_tree.heading('content_preview', text='Content Preview')
        self.chunks_tree.heading('character_count', text='Chars')
        self.chunks_tree.heading('created_at', text='Created')

        # Set column widths
        self.chunks_tree.column('#0', width=50)
        self.chunks_tree.column('chunk_index', width=60)
        self.chunks_tree.column('content_preview', width=500)
        self.chunks_tree.column('character_count', width=80)
        self.chunks_tree.column('created_at', width=150)

        # Add scrollbars
        v_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=self.chunks_tree.yview)
        h_scrollbar = ttk.Scrollbar(grid_frame, orient=tk.HORIZONTAL, command=self.chunks_tree.xview)
        self.chunks_tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)

        # Pack grid and scrollbars
        self.chunks_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')

        # Configure grid weights
        grid_frame.grid_rowconfigure(0, weight=1)
        grid_frame.grid_columnconfigure(0, weight=1)

        # Close button
        ttk.Button(self.window, text="Close", command=self.window.destroy).pack(pady=10)

    def refresh_chunks(self):
        """Refresh chunks display"""
        # Clear existing items
        for item in self.chunks_tree.get_children():
            self.chunks_tree.delete(item)

        try:
            chunks = self.db_manager.execute_query('''
                SELECT id, chunk_index, chunk_content, created_at
                FROM context_chunks
                WHERE context_id = ?
                ORDER BY chunk_index
            ''', (self.context_id,))

            for chunk in chunks:
                chunk_id, chunk_index, chunk_content, created_at = chunk

                # Create preview (first 100 chars)
                content_preview = chunk_content[:100] + ("..." if len(chunk_content) > 100 else "")
                character_count = len(chunk_content)

                self.chunks_tree.insert(
                    '',
                    'end',
                    text=str(chunk_id),
                    values=(chunk_index, content_preview, character_count, created_at)
                )

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to load chunks: {e}")

    def add_chunk(self):
        """Add a new chunk to the context"""
        dialog = AddChunkDialog(self.window, 1150)  # 1150 character limit as per instructions
        new_content = dialog.show()

        if new_content:
            try:
                # Get the next chunk index
                result = self.db_manager.execute_query(
                    "SELECT COALESCE(MAX(chunk_index), -1) + 1 FROM context_chunks WHERE context_id = ?",
                    (self.context_id,)
                )
                next_index = result[0][0] if result else 0

                # Get session and project IDs from context
                context_info = self.db_manager.execute_query(
                    "SELECT session_id, project_id FROM contexts WHERE id = ?",
                    (self.context_id,)
                )

                if context_info:
                    session_id, project_id = context_info[0]

                    # Insert new chunk
                    self.db_manager.execute_update('''
                        INSERT INTO context_chunks
                        (context_id, chunk_index, chunk_content, agent_id, session_id, project_id)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (self.context_id, next_index, new_content, self.agent_id, session_id, project_id))

                    self.refresh_chunks()
                    messagebox.showinfo("Success", "Chunk added successfully")

            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to add chunk: {e}")

    def edit_chunk(self):
        """Edit selected chunk"""
        selection = self.chunks_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a chunk to edit")
            return

        chunk_id = self.chunks_tree.item(selection[0])['text']
        try:
            result = self.db_manager.execute_query(
                "SELECT chunk_content FROM context_chunks WHERE id = ?",
                (chunk_id,)
            )

            if result:
                current_content = result[0][0]
                dialog = EditChunkDialog(self.window, current_content, 1150)
                new_content = dialog.show()

                if new_content is not None:
                    self.db_manager.execute_update(
                        "UPDATE context_chunks SET chunk_content = ? WHERE id = ?",
                        (new_content, chunk_id)
                    )
                    self.refresh_chunks()
                    messagebox.showinfo("Success", "Chunk updated successfully")

        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to edit chunk: {e}")

    def delete_chunk(self):
        """Delete selected chunk"""
        selection = self.chunks_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a chunk to delete")
            return

        chunk_id = self.chunks_tree.item(selection[0])['text']

        if messagebox.askyesno("Confirm Deletion", "Delete selected chunk?"):
            try:
                self.db_manager.execute_update(
                    "DELETE FROM context_chunks WHERE id = ?", (chunk_id,)
                )
                self.refresh_chunks()
                messagebox.showinfo("Success", "Chunk deleted successfully")

            except Exception as e:
                messagebox.showerror("Database Error", f"Failed to delete chunk: {e}")


class AddChunkDialog:
    """Dialog for adding a new chunk"""

    def __init__(self, parent, char_limit):
        self.parent = parent
        self.char_limit = char_limit
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Add New Chunk")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets()

    def create_widgets(self):
        """Create widgets for dialog"""
        # Instructions
        ttk.Label(
            self.dialog,
            text=f"Enter chunk content (max {self.char_limit} characters):",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Character counter
        self.char_count_var = tk.StringVar()
        self.char_count_label = ttk.Label(self.dialog, textvariable=self.char_count_var)
        self.char_count_label.pack(anchor=tk.W, padx=10)

        # Text editor
        text_frame = ttk.Frame(self.dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind text change event
        self.text_widget.bind('<KeyRelease>', self.update_char_count)
        self.text_widget.bind('<Button-1>', self.update_char_count)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save", command=self.on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        # Initial character count
        self.update_char_count()

    def update_char_count(self, event=None):
        """Update character count display"""
        content = self.text_widget.get('1.0', tk.END).rstrip('\n')
        char_count = len(content)
        self.char_count_var.set(f"Characters: {char_count}/{self.char_limit}")

        # Color code based on limit
        if char_count > self.char_limit:
            self.char_count_label.configure(foreground='red')
        elif char_count > self.char_limit * 0.9:
            self.char_count_label.configure(foreground='orange')
        else:
            self.char_count_label.configure(foreground='green')

    def show(self):
        """Show dialog and return result"""
        self.parent.wait_window(self.dialog)
        return self.result

    def on_save(self):
        """Handle save button"""
        content = self.text_widget.get('1.0', tk.END).strip()
        if len(content) > self.char_limit:
            messagebox.showerror("Error", f"Content exceeds {self.char_limit} character limit")
            return
        if not content:
            messagebox.showerror("Error", "Content cannot be empty")
            return

        self.result = content
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()


class EditChunkDialog:
    """Dialog for editing an existing chunk"""

    def __init__(self, parent, current_content, char_limit):
        self.parent = parent
        self.char_limit = char_limit
        self.result = None
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Edit Chunk")
        self.dialog.geometry("800x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self.create_widgets(current_content)

    def create_widgets(self, current_content):
        """Create widgets for dialog"""
        # Instructions
        ttk.Label(
            self.dialog,
            text=f"Edit chunk content (max {self.char_limit} characters):",
            font=("Arial", 10, "bold")
        ).pack(anchor=tk.W, padx=10, pady=(10, 5))

        # Character counter
        self.char_count_var = tk.StringVar()
        self.char_count_label = ttk.Label(self.dialog, textvariable=self.char_count_var)
        self.char_count_label.pack(anchor=tk.W, padx=10)

        # Text editor
        text_frame = ttk.Frame(self.dialog)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))

        self.text_widget = tk.Text(text_frame, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.text_widget.yview)
        self.text_widget.configure(yscrollcommand=scrollbar.set)

        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Insert current content
        self.text_widget.insert('1.0', current_content)

        # Bind text change event
        self.text_widget.bind('<KeyRelease>', self.update_char_count)
        self.text_widget.bind('<Button-1>', self.update_char_count)

        # Buttons
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(pady=10)

        ttk.Button(button_frame, text="Save", command=self.on_save).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.on_cancel).pack(side=tk.LEFT, padx=5)

        # Initial character count
        self.update_char_count()

    def update_char_count(self, event=None):
        """Update character count display"""
        content = self.text_widget.get('1.0', tk.END).rstrip('\n')
        char_count = len(content)
        self.char_count_var.set(f"Characters: {char_count}/{self.char_limit}")

        # Color code based on limit
        if char_count > self.char_limit:
            self.char_count_label.configure(foreground='red')
        elif char_count > self.char_limit * 0.9:
            self.char_count_label.configure(foreground='orange')
        else:
            self.char_count_label.configure(foreground='green')

    def show(self):
        """Show dialog and return result"""
        self.parent.wait_window(self.dialog)
        return self.result

    def on_save(self):
        """Handle save button"""
        content = self.text_widget.get('1.0', tk.END).strip()
        if len(content) > self.char_limit:
            messagebox.showerror("Error", f"Content exceeds {self.char_limit} character limit")
            return

        self.result = content
        self.dialog.destroy()

    def on_cancel(self):
        """Handle cancel button"""
        self.dialog.destroy()