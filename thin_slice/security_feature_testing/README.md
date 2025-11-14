# Security Feature Tests

This folder contains **thin-slice tests** for the security features of the project.  
These tests validate that each technology works correctly and is compatible with others.

---

## Features Covered

| Feature                     | Tested By                            |
|-----------------------------|--------------------------------------|
| Authentication & RBAC       | `test_auth_and_rbac.py`              |
| Encryption & Secrets        | `test_encryption_and_secrets.py`     |
| Input Sanitization          | `test_input_sanitization.py`         |
| Transport Security (HTTPS)  | `test_transport_security.py`         |
| API Integration Security    | `test_api_integration_security.py`   |
| End-to-End Thin-Slice Flow  | `test_thin_slice_e2e.py`             |

---

## Prerequisites

## Install all dependencies before running the tests:
pip install -r requirements.txt


## How to Run the Tests
Run all tests:

python -m pytest thin_slice/security_feature_testing

## Run all tests with verbose output:

python -m pytest -v thin_slice/security_feature_testing

## Run a single test script (example):

python -m pytest thin_slice/security_feature_testing/test_auth_and_rbac.py