# Employee Lookup API — Deployment Guide

Serverless REST API using AWS Lambda (Python), API Gateway, and Amazon RDS PostgreSQL.

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| AWS CLI (v2) | Deploy resources |
| Python 3.12 | Lambda runtime |
| `pip` | Package dependencies |
| PostgreSQL client (`psql`) | Run SQL scripts against RDS |
| An existing VPC with private subnets | Network for RDS + Lambda |

---

## Step 1 — Set Up the RDS PostgreSQL Database

### 1a. Create an RDS PostgreSQL instance (if not already done)

In the AWS Console or via CLI, create a PostgreSQL 15 instance in a private subnet. Note the:
- Endpoint hostname (`DB_HOST`)
- Port (default `5432`)
- Database name (`DB_NAME`)
- Master username (`DB_USER`)
- Master password (`DB_PASSWORD`)

### 1b. Create the schema and seed data

Connect to the database using `psql`:

```bash
psql -h project-incentives.c6ls0ciwccay.us-east-1.rds.amazonaws.com -U master -d postgres -f sql/01_schema.sql
psql -h project-incentives.c6ls0ciwccay.us-east-1.rds.amazonaws.com -U master -d postgres -f sql/02_seed.sql
```

Verify:

```sql
SELECT * FROM employee;
```

Expected output:
```
 id |       name
----+------------------
  1 | John Doe
  2 | Jane Smith
  3 | Michael Johnson
```

---

## Step 2 — Package the Lambda Function

Lambda requires all dependencies to be bundled in the deployment ZIP.

```bash
# From the project root
cd employee-lookup-api

# Install runtime dependency into a package/ directory
pip install psycopg2-binary==2.9.9 --target package/ --quiet

# Copy source files into the package
cp src/*.py package/

# Create the deployment ZIP
cd package
zip -r ../lambda_function.zip .
cd ..
```

The resulting `lambda_function.zip` contains:
- `handler.py` (Lambda entry point)
- `db.py`, `validation.py`, `response.py`, `log.py`
- `psycopg2` and its dependencies

---

## Step 3 — Create the IAM Role for Lambda

The Lambda function needs permissions to write logs to CloudWatch and to reach RDS
(network-level — no IAM policy needed for the DB connection itself).

```bash
# Create the role
aws iam create-role \
  --role-name employee-lookup-lambda-role \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach the managed policy for CloudWatch Logs + VPC networking
aws iam attach-role-policy \
  --role-name employee-lookup-lambda-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole
```

Note the role ARN for the next step.

---

## Step 4 — Create the Lambda Function

Replace the placeholder values with your actual resource identifiers.

```bash
aws lambda create-function \
  --function-name employee-lookup-api \
  --runtime python3.12 \
  --role arn:aws:iam::347379785880:role/employee-lookup-lambda-role \
  --handler handler.lambda_handler \
  --zip-file fileb://lambda_function.zip \
  --timeout 30 \
  --memory-size 256 \
  --vpc-config SubnetIds=subnet-0959bb7c7a339d527,subnet-01ff294592d06aefd,subnet-01708aad14b8ced11,SecurityGroupIds=sg-0f72b178e541d6b3f,sg-0f72b178e541d6b3f \
  --environment Variables="{
    DB_HOST=project-incentives.c6ls0ciwccay.us-east-1.rds.amazonaws.com,
    DB_PORT=5432,
    DB_NAME=postgres,
    DB_USER=postgres,
    DB_PASSWORD=************
  }"
```

> **Security note:** For production, store `DB_PASSWORD` in AWS Secrets Manager or
> Parameter Store (SecureString) and retrieve it at Lambda startup rather than
> injecting it as a plain environment variable.

To update the function code after changes:

```bash
aws lambda update-function-code \
  --function-name employee-lookup-api \
  --zip-file fileb://lambda_function.zip
```

---

## Step 5 — Configure API Gateway

### 5a. Create the REST API

```bash
aws apigateway create-rest-api \
  --name "employee-lookup-api" \
  --description "Employee Lookup REST API" \
  --endpoint-configuration types=REGIONAL
```

Note the `id` field — this is your `<API_ID>`.

### 5b. Get the root resource ID

```bash
aws apigateway get-resources --rest-api-id <API_ID>
```

Note the `id` of the root (`/`) resource — this is `<ROOT_RESOURCE_ID>`.

### 5c. Create the /employees resource

```bash
aws apigateway create-resource \
  --rest-api-id <API_ID> \
  --parent-id <ROOT_RESOURCE_ID> \
  --path-part employees
```

Note the new resource `id` — this is `<EMPLOYEES_RESOURCE_ID>`.

### 5d. Create the /employees/{id} resource

```bash
aws apigateway create-resource \
  --rest-api-id <API_ID> \
  --parent-id <EMPLOYEES_RESOURCE_ID> \
  --path-part "{id}"
```

Note the new resource `id` — this is `<EMPLOYEE_ID_RESOURCE_ID>`.

### 5e. Add GET method to /employees (Lambda Proxy Integration)

```bash
# Create the method
aws apigateway put-method \
  --rest-api-id <API_ID> \
  --resource-id <EMPLOYEES_RESOURCE_ID> \
  --http-method GET \
  --authorization-type NONE

# Wire up Lambda Proxy Integration
aws apigateway put-integration \
  --rest-api-id <API_ID> \
  --resource-id <EMPLOYEES_RESOURCE_ID> \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:<REGION>:lambda:path/2015-03-31/functions/arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:employee-lookup-api/invocations
```

### 5f. Add GET method to /employees/{id} (Lambda Proxy Integration)

```bash
# Create the method
aws apigateway put-method \
  --rest-api-id <API_ID> \
  --resource-id <EMPLOYEE_ID_RESOURCE_ID> \
  --http-method GET \
  --authorization-type NONE

# Wire up Lambda Proxy Integration
aws apigateway put-integration \
  --rest-api-id <API_ID> \
  --resource-id <EMPLOYEE_ID_RESOURCE_ID> \
  --http-method GET \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:<REGION>:lambda:path/2015-03-31/functions/arn:aws:lambda:<REGION>:<ACCOUNT_ID>:function:employee-lookup-api/invocations
```

### 5g. Grant API Gateway permission to invoke Lambda

```bash
aws lambda add-permission \
  --function-name employee-lookup-api \
  --statement-id apigateway-invoke-list \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:<REGION>:<ACCOUNT_ID>:<API_ID>/*/GET/employees"

aws lambda add-permission \
  --function-name employee-lookup-api \
  --statement-id apigateway-invoke-detail \
  --action lambda:InvokeFunction \
  --principal apigateway.amazonaws.com \
  --source-arn "arn:aws:execute-api:<REGION>:<ACCOUNT_ID>:<API_ID>/*/GET/employees/*"
```

### 5h. Deploy the API

```bash
aws apigateway create-deployment \
  --rest-api-id <API_ID> \
  --stage-name v1
```

Your base URL is:
```
https://<API_ID>.execute-api.<REGION>.amazonaws.com/v1
```

---

## Step 6 — Verify the Endpoints

```bash
BASE_URL="https://6mbjnmirla.execute-api.us-east-1.amazonaws.com/v1"

# List all employees
curl -s "$BASE_URL/employees" | python3 -m json.tool

# Get employee by ID
curl -s "$BASE_URL/employees/1" | python3 -m json.tool

# Expect 404 for unknown ID
curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/employees/9999"

# Expect 400 for invalid ID
curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/employees/abc"
```

Expected responses:

```json
// GET /employees → 200
[
  {"id": 1, "name": "John Doe"},
  {"id": 2, "name": "Jane Smith"},
  {"id": 3, "name": "Michael Johnson"}
]

// GET /employees/1 → 200
{"id": 1, "name": "John Doe"}

// GET /employees/9999 → 404
{"message": "Employee not found"}

// GET /employees/abc → 400
{"message": "Employee ID must be a numeric value, got: 'abc'"}
```

---

## API Gateway Resource Summary

| Resource | Method | Integration | Lambda resource key |
|----------|--------|-------------|---------------------|
| `/employees` | GET | AWS_PROXY | `/employees` |
| `/employees/{id}` | GET | AWS_PROXY | `/employees/{id}` |

Both routes use **Lambda Proxy Integration** — API Gateway passes the full request
event to Lambda and returns the Lambda response dict directly to the client.

---

## Lambda Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_HOST` | RDS instance endpoint | `mydb.abc123.us-east-1.rds.amazonaws.com` |
| `DB_PORT` | PostgreSQL port | `5432` |
| `DB_NAME` | Database name | `employees` |
| `DB_USER` | Database username | `admin` |
| `DB_PASSWORD` | Database password | (use Secrets Manager in production) |

---

## Running Unit Tests Locally

No AWS credentials or database connection required.

```bash
cd employee-lookup-api
pip install pytest==8.2.2 pytest-mock==3.14.0
python -m pytest tests/unit/ -v
```

Expected: **92 passed**.

---

## HTTP Status Code Reference

| Code | Condition |
|------|-----------|
| 200 | Successful read |
| 400 | Invalid path parameter (non-numeric, zero, negative, >999999999) |
| 403 | Request to undefined path or method (API Gateway default) |
| 404 | Employee not found |
| 405 | Non-GET method on a defined path |
| 500 | DB error, config error, or unexpected exception |
| 502 | Lambda returned a malformed proxy response (API Gateway default) |

---

## Project Structure

```
employee-lookup-api/
├── src/
│   ├── handler.py          # Lambda entry point — routing and error handling
│   ├── db.py               # DB connection (retry/timeout) and queries
│   ├── validation.py       # Input and config validation
│   ├── response.py         # Response builder (all HTTP status codes)
│   └── log.py              # Structured CloudWatch logging with credential masking
├── tests/
│   └── unit/
│       ├── test_handler.py
│       ├── test_response.py
│       ├── test_validation.py
│       └── test_log.py
├── sql/
│   ├── 01_schema.sql       # CREATE TABLE employee
│   ├── 02_seed.sql         # Sample data (John Doe, Jane Smith, Michael Johnson)
│   └── 03_queries.sql      # Reference SQL queries used at runtime
├── conftest.py             # pytest path configuration
├── requirements.txt        # psycopg2-binary (runtime) + pytest (dev)
└── DEPLOYMENT.md           # This file
```
