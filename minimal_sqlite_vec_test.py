#!/usr/bin/env python3
"""
Minimal test for sqlite-vec functionality
This file can be used to verify that sqlite-vec is working correctly.
"""

import sqlite3
import numpy as np

def test_sqlite_vec_basic():
    """Test basic sqlite-vec functionality with in-memory database"""
    print("Testing sqlite-vec functionality...")

    try:
        # Import sqlite-vec
        import sqlite_vec
        print("PASS: sqlite_vec imported successfully")

        # Use in-memory database to avoid file locking issues
        with sqlite3.connect(":memory:") as conn:
            # Enable extension loading
            conn.enable_load_extension(True)
            # Load sqlite-vec extension
            conn.load_extension(sqlite_vec.loadable_path())
            print("PASS: sqlite_vec extension loaded successfully")

            cursor = conn.cursor()

            # Create vector table
            cursor.execute('''
                CREATE VIRTUAL TABLE test_vec
                USING vec0(
                    embedding float[3]
                )
            ''')
            print("PASS: Created vector virtual table")

            # Test inserting a small vector
            test_vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)

            cursor.execute('''
                INSERT INTO test_vec (rowid, embedding)
                VALUES (?, ?)
            ''', (1, test_vector.tobytes()))

            conn.commit()
            print("PASS: Inserted test vector")

            # Test querying
            cursor.execute("SELECT COUNT(*) FROM test_vec")
            count = cursor.fetchone()[0]
            print(f"PASS: Vector table has {count} rows")

            # Test retrieving vector
            cursor.execute("SELECT rowid FROM test_vec WHERE rowid = 1")
            result = cursor.fetchone()
            if result:
                print("PASS: Successfully retrieved vector")
            else:
                print("FAIL: Could not retrieve vector")
                return False

            print("PASS: All sqlite-vec basic tests completed successfully!")
            return True

    except ImportError as e:
        print(f"FAIL: Failed to import sqlite_vec: {e}")
        return False
    except Exception as e:
        print(f"FAIL: sqlite-vec test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Minimal SQLite-Vec Test ===\n")

    result = test_sqlite_vec_basic()

    print(f"\nResult: {'SUCCESS' if result else 'FAILED'}")

    if result:
        print("\nsqlite-vec is working correctly and can be used in the MCP server!")
    else:
        print("\nsqlite-vec has issues. Check the error messages above.")