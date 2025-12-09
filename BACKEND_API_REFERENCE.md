# Backend API Reference

**Web Agent Dynamic Suite v2 - Complete REST API Documentation**

Version: 2.0
Last Updated: 2025-11-23

---

## Table of Contents

1. [Overview](#overview)
2. [Base URL](#base-url)
3. [Authentication](#authentication)
4. [Response Format](#response-format)
5. [API Endpoints](#api-endpoints)
   - [Environment](#environment-apis)
   - [Users](#user-apis)
   - [Products](#product-apis)
   - [Orders](#order-apis)
   - [Accounts & Banking](#accounts--banking-apis)
   - [Cards](#card-apis)
   - [Transactions](#transaction-apis)
   - [Autopay](#autopay-apis)
   - [Bills](#bills-apis)
   - [Permits](#permits-apis)
   - [Applications](#applications-apis)
   - [Appointments](#appointments-apis)
   - [Returns](#returns-apis)
   - [Settlements](#settlements-apis)
   - [Merchant Bindings](#merchant-bindings-apis)
   - [Memory KV Store](#memory-kv-apis)
   - [Task Executions](#task-executions-apis)
6. [Error Codes](#error-codes)
7. [Examples](#examples)

---

## Overview

The Web Agent Dynamic Suite v2 backend provides a comprehensive REST API for managing:
- E-commerce operations (shop.local)
- Banking and financial services (bank.local)
- Government services (gov.local)
- Cross-site utilities and state management

All endpoints support CORS and return JSON responses.

---

## Base URL

```
http://localhost:8014
```

---

## Authentication

Currently, the API uses user_id=1 for all requests (demo mode). Future versions will support session-based authentication.

---

## Response Format

### Success Response
```json
{
  "success": true,
  "data_key": "data_value"
}
```

### Error Response
```json
{
  "success": false,
  "error": "Error message description"
}
```

---

## API Endpoints

### Environment APIs

#### GET /api/env
Get complete environment state including accounts, orders, and system config.

**Response:**
```json
{
  "accounts": {
    "checking": {"balance": 5000.00, "currency": "USD"},
    "savings": {"balance": 10000.00, "currency": "USD"}
  },
  "orders": {},
  "permits": {}
}
```

#### GET /api/env/query
Query environment state using dot notation path.

**Parameters:**
- `path` (required): Dot-notation path, e.g., "accounts.checking.balance"

**Supports:**
- Nested keys: `accounts.checking.balance`
- Wildcards: `orders.*.state`
- Array indices: `items[0].name`

**Example:**
```bash
GET /api/env/query?path=accounts.checking.balance
```

**Response:**
```json
{
  "success": true,
  "path": "accounts.checking.balance",
  "value": 5000.00
}
```

#### POST /api/reset
Reset environment to initial state.

**Response:**
```json
{
  "ok": true
}
```

---

### User APIs

#### GET /api/user
Get current user information with memory/preferences.

**Response:**
```json
{
  "success": true,
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "test@example.com",
    "created_at": "2025-11-16 08:45:01",
    "memory": {
      "address.primary": "123 Main St, Apt 5B",
      "payment.cards[0].last4": "****7777"
    }
  }
}
```

---

### Product APIs

#### GET /api/products
List products with optional filtering.

**Parameters:**
- `category` (optional): Filter by category
- `search` (optional): Search in product name
- `max_price` (optional): Maximum price filter
- `limit` (optional, default=20): Result limit

**Example:**
```bash
GET /api/products?search=wireless+mouse&max_price=30
```

**Response:**
```json
{
  "success": true,
  "products": [
    {
      "id": 1,
      "sku": "WM-5521",
      "name": "Logitech M185 Wireless Mouse",
      "price": 24.99,
      "category": "electronics",
      "stock": 50,
      "original_price": 29.99,
      "product_id": 1
    }
  ],
  "count": 1
}
```

#### GET /api/products/:sku_or_id
Get product details by SKU or ID.

**Example:**
```bash
GET /api/products/WM-5521
```

**Response:**
```json
{
  "success": true,
  "product": {
    "id": 1,
    "sku": "WM-5521",
    "name": "Logitech M185 Wireless Mouse",
    "price": 24.99,
    "category": "electronics",
    "stock": 50
  }
}
```

---

### Order APIs

#### GET /api/orders
List user's orders.

**Parameters:**
- `user_id` (optional, default=1): User ID
- `limit` (optional, default=20): Result limit

**Response:**
```json
{
  "success": true,
  "orders": [
    {
      "id": "O-10001",
      "user_id": 1,
      "total": 24.99,
      "state": "confirmed",
      "shipping_speed": "standard",
      "shipping_address": "123 Main St, Apt 5B",
      "created_at": "2025-11-23T04:46:21",
      "items": [
        {
          "sku": "WM-5521",
          "quantity": 1,
          "price": 24.99,
          "name": "Logitech M185 Wireless Mouse"
        }
      ]
    }
  ]
}
```

#### GET /api/orders/:order_id
Get order details by ID.

**Example:**
```bash
GET /api/orders/O-10001
```

**Response:**
```json
{
  "success": true,
  "order": {
    "id": "O-10001",
    "user_id": 1,
    "total": 24.99,
    "state": "confirmed",
    "shipping_address": "123 Main St, Apt 5B",
    "items": [...]
  }
}
```

#### POST /api/orders
Create a new order.

**Request Body:**
```json
{
  "user_id": 1,
  "items": [
    {"product_id": 1, "quantity": 1}
  ],
  "shipping_address": "123 Main St, Apt 5B",
  "shipping_speed": "standard"
}
```

**Response:**
```json
{
  "success": true,
  "order_id": "O-10001",
  "order_number": "O-10001",
  "total": 24.99
}
```

#### PUT /api/orders/:order_id
Update order status or shipping speed.

**Request Body:**
```json
{
  "state": "shipped",
  "shipping_speed": "express"
}
```

**Response:**
```json
{
  "success": true,
  "order_id": "O-10001",
  "state": "shipped"
}
```

---

### Accounts & Banking APIs

#### GET /api/accounts
Get user's bank accounts.

**Parameters:**
- `user_id` (optional, default=1)

**Response:**
```json
{
  "success": true,
  "accounts": [
    {
      "id": 1,
      "user_id": 1,
      "type": "checking",
      "balance": 5000.00,
      "currency": "USD"
    },
    {
      "id": 2,
      "user_id": 1,
      "type": "savings",
      "balance": 10000.00,
      "currency": "USD"
    }
  ]
}
```

---

### Card APIs

#### GET /api/cards
Get user's payment cards.

**Parameters:**
- `user_id` (optional, default=1)

**Response:**
```json
{
  "success": true,
  "cards": [
    {
      "id": 1,
      "user_id": 1,
      "last4": "1234",
      "type": "physical",
      "state": "active",
      "exp_date": "12/2027"
    }
  ]
}
```

#### POST /api/cards/activate
Activate a new card.

**Request Body:**
```json
{
  "new_last4": "7777"
}
```

**Response:**
```json
{
  "success": true,
  "exp_date": "12/2029"
}
```

#### POST /api/cards/deactivate
Deactivate a card.

**Request Body:**
```json
{
  "last4": "1234"
}
```

**Response:**
```json
{
  "success": true
}
```

---

### Transaction APIs

#### GET /api/transactions
Get account transactions.

**Parameters:**
- `account_id` (optional, default=1)
- `days` (optional, default=30)

**Response:**
```json
{
  "success": true,
  "transactions": [
    {
      "id": 1,
      "account_id": 1,
      "amount": -24.99,
      "type": "debit",
      "description": "Order O-10001",
      "created_at": "2025-11-23T04:46:21"
    }
  ]
}
```

---

### Autopay APIs

#### GET /api/autopay
Get autopay configurations.

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "id": "AP-1234",
      "payee": "utilities",
      "account_type": "checking",
      "amount": 150.00,
      "frequency": "monthly",
      "next_date": "2025-12-01",
      "state": "active"
    }
  ]
}
```

#### POST /api/autopay
Create autopay configuration.

**Request Body:**
```json
{
  "payee": "utilities",
  "account_type": "checking",
  "amount": 150.00,
  "frequency": "monthly",
  "start_date": "2025-12-01"
}
```

**Response:**
```json
{
  "success": true,
  "autopay": {
    "id": "AP-1234",
    "state": "active",
    "payee": "utilities"
  }
}
```

---

### Bills APIs

#### GET /api/bills
Get user's bills.

**Parameters:**
- `user_id` (optional, default=1)

**Response:**
```json
{
  "success": true,
  "bills": [
    {
      "id": 1,
      "user_id": 1,
      "type": "electricity",
      "amount": 85.50,
      "due_date": "2025-12-15",
      "state": "unpaid"
    }
  ]
}
```

#### POST /api/bills/pay
Pay a bill.

**Request Body:**
```json
{
  "bill_id": 1,
  "account_id": 1
}
```

**Response:**
```json
{
  "success": true,
  "bill_id": 1,
  "amount": 85.50,
  "state": "paid"
}
```

---

### Permits APIs

#### GET /api/permits
Get user's permits.

**Parameters:**
- `user_id` (optional, default=1)

**Response:**
```json
{
  "success": true,
  "permits": [
    {
      "id": "RP-2024-77",
      "user_id": 1,
      "type": "residence",
      "state": "active",
      "issue_date": "2024-01-15",
      "expiry_date": "2025-01-15",
      "renewal_eligible": 1
    }
  ]
}
```

#### GET /api/permits/:permit_id
Get permit details.

**Example:**
```bash
GET /api/permits/RP-2024-77
```

#### POST /api/permits/apply
Submit permit application.

**Response:**
```json
{
  "success": true,
  "application_id": "APP-1234"
}
```

---

### Applications APIs

#### GET /api/applications
Get user's applications.

**Parameters:**
- `user_id` (optional, default=1)

**Response:**
```json
{
  "success": true,
  "applications": [
    {
      "id": "APP-1234",
      "user_id": 1,
      "type": "parking_permit",
      "state": "submitted",
      "created_at": "2025-11-23T04:46:21"
    }
  ]
}
```

---

### Appointments APIs

#### GET /api/appointments
Get user's appointments.

**Parameters:**
- `user_id` (optional, default=1)

**Response:**
```json
{
  "success": true,
  "appointments": [
    {
      "id": "APT-1234",
      "user_id": 1,
      "application_id": "APP-1234",
      "date": "2025-12-01",
      "time": "10:00",
      "state": "booked"
    }
  ]
}
```

#### GET /api/appointments/:appointment_id
Get appointment details.

#### POST /api/appointments
Create a new appointment.

**Request Body:**
```json
{
  "user_id": 1,
  "application_id": "APP-1234",
  "date": "2025-12-01",
  "time": "10:00"
}
```

**Response:**
```json
{
  "success": true,
  "appointment_id": "APT-1234",
  "date": "2025-12-01",
  "time": "10:00",
  "state": "booked"
}
```

#### PUT /api/appointments/:appointment_id
Update appointment.

**Request Body:**
```json
{
  "state": "completed",
  "date": "2025-12-02",
  "time": "14:00"
}
```

**Response:**
```json
{
  "success": true,
  "appointment_id": "APT-1234"
}
```

---

### Returns APIs

#### GET /api/returns
Get user's return requests.

**Parameters:**
- `user_id` (optional, default=1)

**Response:**
```json
{
  "success": true,
  "returns": [
    {
      "id": "R-50001",
      "order_id": "O-10001",
      "user_id": 1,
      "reason": "defective",
      "state": "submitted",
      "refund_amount": 24.99
    }
  ]
}
```

#### POST /api/returns
Create a return request.

**Request Body:**
```json
{
  "order_id": "O-10001",
  "user_id": 1,
  "reason": "defective"
}
```

**Response:**
```json
{
  "success": true,
  "return_id": "R-50001",
  "state": "submitted"
}
```

---

### Settlements APIs

#### GET /api/settlements
Get expense settlements.

**Parameters:**
- `user_id` (optional, default=1)
- `period` (optional): Filter by period, e.g., "2025-11"

**Response:**
```json
{
  "success": true,
  "settlements": [
    {
      "id": "SETTLE-2025-11",
      "user_id": 1,
      "period": "2025-11",
      "members": ["Alice", "Bob", "Carol"],
      "total_amount": 450.00,
      "state": "pending"
    }
  ]
}
```

#### GET /api/settlements/:settlement_id
Get settlement details.

#### POST /api/settlements
Create expense settlement.

**Request Body:**
```json
{
  "user_id": 1,
  "period": "2025-11",
  "members": ["Alice", "Bob", "Carol"],
  "total_amount": 450.00
}
```

**Response:**
```json
{
  "success": true,
  "settlement_id": "SETTLE-2025-11",
  "total_amount": 450.00,
  "state": "pending"
}
```

---

### Merchant Bindings APIs

#### GET /api/merchant_bindings
Get payment method bindings for merchants.

**Parameters:**
- `user_id` (optional, default=1)
- `merchant` (optional): Filter by merchant

**Response:**
```json
{
  "success": true,
  "bindings": [
    {
      "id": 1,
      "user_id": 1,
      "merchant": "shop.local",
      "card_last4": "1234",
      "binding_type": "default"
    }
  ]
}
```

#### POST /api/merchant_bindings/update
Update merchant binding.

**Request Body:**
```json
{
  "merchant": "shop.local",
  "last4": "7777"
}
```

**Response:**
```json
{
  "success": true
}
```

---

### Memory KV APIs

#### GET /api/memory
Get all keys or specific key from long-term memory.

**Parameters:**
- `key` (optional): Get specific key
- `pattern` (optional): Pattern matching with SQL LIKE syntax

**Examples:**
```bash
GET /api/memory?key=orders.last.id
GET /api/memory?pattern=address.%
```

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "key": "orders.last.id",
      "value": "O-10001",
      "ts": "2025-11-23T04:46:21"
    }
  ]
}
```

#### POST /api/memory
Store key-value pair in memory.

**Request Body:**
```json
{
  "key": "user.preference.theme",
  "value": "dark",
  "source": "user"
}
```

**Response:**
```json
{
  "success": true,
  "key": "user.preference.theme",
  "value": "dark"
}
```

#### DELETE /api/memory/:key
Delete key from memory.

**Example:**
```bash
DELETE /api/memory/user.preference.theme
```

**Response:**
```json
{
  "success": true,
  "key": "user.preference.theme"
}
```

---

### Task Executions APIs

#### GET /api/task_executions
Get task execution logs.

**Parameters:**
- `task_id` (optional): Filter by task ID
- `state` (optional): Filter by state (running, completed, failed)
- `limit` (optional, default=50)

**Response:**
```json
{
  "success": true,
  "executions": [
    {
      "id": 1,
      "task_id": "B1-shopping",
      "agent_version": "v2.0",
      "state": "completed",
      "started_at": "2025-11-23T04:46:21",
      "completed_at": "2025-11-23T04:48:15",
      "steps_completed": 10,
      "steps_total": 10
    }
  ]
}
```

#### POST /api/task_executions
Start a new task execution.

**Request Body:**
```json
{
  "task_id": "B1-shopping",
  "agent_version": "v2.0",
  "steps_total": 10
}
```

**Response:**
```json
{
  "success": true,
  "execution_id": 1,
  "task_id": "B1-shopping",
  "state": "running"
}
```

#### PUT /api/task_executions/:execution_id
Update task execution status.

**Request Body:**
```json
{
  "state": "completed",
  "steps_completed": 10
}
```

**Response:**
```json
{
  "success": true,
  "execution_id": 1
}
```

---

## Error Codes

| HTTP Code | Description |
|-----------|-------------|
| 200 | Success |
| 400 | Bad Request - Missing required parameters |
| 404 | Not Found - Resource doesn't exist |
| 500 | Internal Server Error |

---

## Examples

### Complete Shopping Flow

```bash
# 1. Search for products
curl "http://localhost:8014/api/products?search=wireless+mouse&max_price=30"

# 2. Get product details
curl "http://localhost:8014/api/products/WM-5521"

# 3. Create order
curl -X POST "http://localhost:8014/api/orders" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "items": [{"product_id": 1, "quantity": 1}],
    "shipping_address": "123 Main St, Apt 5B"
  }'

# 4. Get order details
curl "http://localhost:8014/api/orders/O-10001"

# 5. Store order ID in memory
curl -X POST "http://localhost:8014/api/memory" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "orders.last.id",
    "value": "O-10001",
    "source": "agent"
  }'
```

### Bill Payment Flow

```bash
# 1. Get unpaid bills
curl "http://localhost:8014/api/bills?user_id=1"

# 2. Get account balance
curl "http://localhost:8014/api/accounts?user_id=1"

# 3. Pay bill
curl -X POST "http://localhost:8014/api/bills/pay" \
  -H "Content-Type: application/json" \
  -d '{
    "bill_id": 1,
    "account_id": 1
  }'

# 4. Verify transaction
curl "http://localhost:8014/api/transactions?account_id=1"
```

### Permit Renewal Flow

```bash
# 1. Get permits
curl "http://localhost:8014/api/permits?user_id=1"

# 2. Apply for renewal
curl -X POST "http://localhost:8014/api/permits/apply"

# 3. Book appointment
curl -X POST "http://localhost:8014/api/appointments" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1,
    "application_id": "APP-1234",
    "date": "2025-12-01",
    "time": "10:00"
  }'

# 4. Get appointment confirmation
curl "http://localhost:8014/api/appointments?user_id=1"
```

---

## Advanced Features

### Environment Path Queries

Query nested environment state:

```bash
# Get specific account balance
curl "http://localhost:8014/api/env/query?path=accounts.checking.balance"

# Get all order states
curl "http://localhost:8014/api/env/query?path=orders.*.state"

# Get first item in array
curl "http://localhost:8014/api/env/query?path=orders.items[0].name"
```

### Memory Pattern Matching

Search memory keys:

```bash
# Get all address-related keys
curl "http://localhost:8014/api/memory?pattern=address.%"

# Get all payment-related keys
curl "http://localhost:8014/api/memory?pattern=payment.%"

# Get all order-related keys
curl "http://localhost:8014/api/memory?pattern=orders.%"
```

---

## API Coverage Summary

| Category | Endpoints | Methods |
|----------|-----------|---------|
| Environment | 3 | GET, POST |
| Users | 1 | GET |
| Products | 2 | GET |
| Orders | 3 | GET, POST, PUT |
| Accounts | 1 | GET |
| Cards | 3 | GET, POST |
| Transactions | 1 | GET |
| Autopay | 2 | GET, POST |
| Bills | 2 | GET, POST |
| Permits | 3 | GET, POST |
| Applications | 1 | GET |
| Appointments | 3 | GET, POST, PUT |
| Returns | 2 | GET, POST |
| Settlements | 3 | GET, POST |
| Merchant Bindings | 2 | GET, POST |
| Memory KV | 3 | GET, POST, DELETE |
| Task Executions | 3 | GET, POST, PUT |

**Total**: 37 API endpoints across 17 categories

---

## Notes

- All APIs support CORS for cross-origin requests
- Default user_id is 1 for all authenticated requests
- All datetime values are in ISO 8601 format
- All monetary amounts are in decimal format (e.g., 24.99)
- Order IDs use format: O-XXXXX
- Return IDs use format: R-XXXXX
- Appointment IDs use format: APT-XXXX
- Settlement IDs use format: SETTLE-YYYY-MM

---

## Future Enhancements

- [ ] Session-based authentication
- [ ] Rate limiting
- [ ] API versioning (v2, v3)
- [ ] Webhooks for state changes
- [ ] GraphQL endpoint
- [ ] Batch operations
- [ ] Real-time subscriptions via WebSocket

---

**Generated**: 2025-11-23
**Maintainer**: Web Agent Dynamic Suite Team
