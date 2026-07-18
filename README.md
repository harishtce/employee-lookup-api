Scenario


Your company maintains employee information in a PostgreSQL database hosted on Amazon
RDS. You are required to build a simple serverless API that retrieves employee data from the
database.

Requirements


Create an AWS Lambda function that connects to the PostgreSQL database and expose it through
Amazon API Gateway. Implement GET /employees and GET /employees/{id}.

Deliverables


1. Lambda source code. 2. SQL queries used. 3. API Gateway configuration. 4. Working endpoints
GET /employees and GET /employees/{id}.


Output

1. https://6mbjnmirla.execute-api.us-east-1.amazonaws.com/v1/employees
  
2. https://6mbjnmirla.execute-api.us-east-1.amazonaws.com/v1/employees/1
   
3. https://6mbjnmirla.execute-api.us-east-1.amazonaws.com/v1/employees/9999
   
4. https://6mbjnmirla.execute-api.us-east-1.amazonaws.com/v1/employees/abc

