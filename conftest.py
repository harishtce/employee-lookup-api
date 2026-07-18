"""
conftest.py — Adds src/ to sys.path so all test files can import the Lambda modules.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
