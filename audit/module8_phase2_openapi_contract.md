``json
{
  "openapi": "3.1.0",
  "info": {
    "title": "ResearchMind API",
    "version": "1.0.0"
  },
  "paths": {
    "/api/v1/health": {
      "get": {
        "tags": [
          "System"
        ],
        "summary": "Health Check",
        "operationId": "health_check_api_v1_health_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api/v1/version": {
      "get": {
        "tags": [
          "System"
        ],
        "summary": "Get Version",
        "operationId": "get_version_api_v1_version_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/login": {
      "post": {
        "tags": [
          "Authentication"
        ],
        "summary": "Login",
        "operationId": "login_api_v1_auth_login_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/UserLogin"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/Token"
                }
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/register": {
      "post": {
        "tags": [
          "Authentication"
        ],
        "summary": "Register",
        "operationId": "register_api_v1_auth_register_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/UserRegister"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/refresh": {
      "post": {
        "tags": [
          "Authentication"
        ],
        "summary": "Refresh Token",
        "operationId": "refresh_token_api_v1_auth_refresh_post",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api/v1/auth/logout": {
      "post": {
        "tags": [
          "Authentication"
        ],
        "summary": "Logout",
        "operationId": "logout_api_v1_auth_logout_post",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api/v1/query/parse": {
      "post": {
        "tags": [
          "Query Engine"
        ],
        "summary": "Parse Query",
        "operationId": "parse_query_api_v1_query_parse_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ParseRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/query/plan": {
      "post": {
        "tags": [
          "Query Engine"
        ],
        "summary": "Plan Query",
        "operationId": "plan_query_api_v1_query_plan_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ParsedQuery"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/query/route": {
      "post": {
        "tags": [
          "Query Engine"
        ],
        "summary": "Route Query",
        "operationId": "route_query_api_v1_query_route_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ParsedQuery"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/query/answer": {
      "post": {
        "tags": [
          "Query Engine"
        ],
        "summary": "Answer Query",
        "operationId": "answer_query_api_v1_query_answer_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/AnswerRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/reviews/generate": {
      "post": {
        "tags": [
          "Synthesis Engine"
        ],
        "summary": "Generate Review",
        "operationId": "generate_review_api_v1_reviews_generate_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ReviewRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/reviews/validate": {
      "post": {
        "tags": [
          "Synthesis Engine"
        ],
        "summary": "Validate Review",
        "operationId": "validate_review_api_v1_reviews_validate_post",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/ReviewResult"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/graph/graph": {
      "get": {
        "tags": [
          "Corpus Graph"
        ],
        "summary": "Get Graph",
        "operationId": "get_graph_api_v1_graph_graph_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api/v1/graph/graph/node/{id}": {
      "get": {
        "tags": [
          "Corpus Graph"
        ],
        "summary": "Get Graph Node",
        "operationId": "get_graph_node_api_v1_graph_graph_node__id__get",
        "parameters": [
          {
            "name": "id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "title": "Id"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/documents/documents": {
      "get": {
        "tags": [
          "Documents"
        ],
        "summary": "Get Documents",
        "operationId": "get_documents_api_v1_documents_documents_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api/v1/documents/document/{id}": {
      "get": {
        "tags": [
          "Documents"
        ],
        "summary": "Get Document",
        "operationId": "get_document_api_v1_documents_document__id__get",
        "parameters": [
          {
            "name": "id",
            "in": "path",
            "required": true,
            "schema": {
              "type": "string",
              "title": "Id"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          },
          "422": {
            "description": "Validation Error",
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            }
          }
        }
      }
    },
    "/api/v1/dashboard/dashboard": {
      "get": {
        "tags": [
          "Dashboard"
        ],
        "summary": "Get Dashboard",
        "operationId": "get_dashboard_api_v1_dashboard_dashboard_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    },
    "/api/v1/monitoring/monitoring": {
      "get": {
        "tags": [
          "Monitoring"
        ],
        "summary": "Get Monitoring",
        "operationId": "get_monitoring_api_v1_monitoring_monitoring_get",
        "responses": {
          "200": {
            "description": "Successful Response",
            "content": {
              "application/json": {
                "schema": {}
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "AnswerRequest": {
        "properties": {
          "query_id": {
            "type": "string",
            "title": "Query Id"
          },
          "raw_query": {
            "type": "string",
            "title": "Raw Query"
          }
        },
        "type": "object",
        "required": [
          "query_id",
          "raw_query"
        ],
        "title": "AnswerRequest"
      },
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "type": "array",
            "title": "Detail"
          }
        },
        "type": "object",
        "title": "HTTPValidationError"
      },
      "ParseRequest": {
        "properties": {
          "raw_query": {
            "type": "string",
            "title": "Raw Query"
          }
        },
        "type": "object",
        "required": [
          "raw_query"
        ],
        "title": "ParseRequest"
      },
      "ParsedQuery": {
        "properties": {
          "raw_query": {
            "type": "string",
            "title": "Raw Query"
          },
          "query_type": {
            "type": "string",
            "title": "Query Type"
          },
          "primary_entity": {
            "anyOf": [
              {
                "$ref": "#/components/schemas/QueryEntity"
              },
              {
                "type": "null"
              }
            ]
          },
          "secondary_entities": {
            "items": {
              "$ref": "#/components/schemas/QueryEntity"
            },
            "type": "array",
            "title": "Secondary Entities"
          },
          "constraints": {
            "items": {
              "$ref": "#/components/schemas/QueryConstraint"
            },
            "type": "array",
            "title": "Constraints"
          },
          "max_hops": {
            "type": "integer",
            "title": "Max Hops",
            "default": 3
          },
          "min_confidence": {
            "type": "number",
            "title": "Min Confidence",
            "default": 0.3
          },
          "include_reasoning": {
            "type": "boolean",
            "title": "Include Reasoning",
            "default": true
          },
          "include_evidence": {
            "type": "boolean",
            "title": "Include Evidence",
            "default": true
          },
          "entities_resolved": {
            "type": "boolean",
            "title": "Entities Resolved",
            "default": false
          },
          "parsing_warnings": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Parsing Warnings"
          }
        },
        "type": "object",
        "required": [
          "raw_query",
          "query_type"
        ],
        "title": "ParsedQuery",
        "description": "A fully parsed and classified query, ready for planning."
      },
      "QueryConstraint": {
        "properties": {
          "field": {
            "type": "string",
            "title": "Field"
          },
          "operator": {
            "type": "string",
            "title": "Operator"
          },
          "value": {
            "title": "Value"
          }
        },
        "type": "object",
        "required": [
          "field",
          "operator",
          "value"
        ],
        "title": "QueryConstraint",
        "description": "A constraint or filter on a query (year, confidence, document, relation_type)."
      },
      "QueryEntity": {
        "properties": {
          "text": {
            "type": "string",
            "title": "Text"
          },
          "entity_type": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Entity Type",
            "description": "method | dataset | metric | document | concept | unknown"
          },
          "cluster_id": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "title": "Cluster Id"
          },
          "confidence": {
            "type": "number",
            "maximum": 1.0,
            "minimum": 0.0,
            "title": "Confidence",
            "default": 0.0
          },
          "is_ambiguous": {
            "type": "boolean",
            "title": "Is Ambiguous",
            "default": false
          },
          "alternatives": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Alternatives"
          }
        },
        "type": "object",
        "required": [
          "text"
        ],
        "title": "QueryEntity",
        "description": "An entity mention extracted from the user's question."
      },
      "ReviewFinding": {
        "properties": {
          "finding_id": {
            "type": "string",
            "title": "Finding Id"
          },
          "finding_type": {
            "type": "string",
            "title": "Finding Type"
          },
          "statement": {
            "type": "string",
            "title": "Statement"
          },
          "confidence": {
            "type": "number",
            "maximum": 1.0,
            "minimum": 0.0,
            "title": "Confidence"
          },
          "evidence_ids": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Evidence Ids"
          },
          "source_document_ids": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Source Document Ids"
          },
          "source_document_titles": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Source Document Titles"
          },
          "supporting_count": {
            "type": "integer",
            "title": "Supporting Count",
            "default": 0
          },
          "contradicting_count": {
            "type": "integer",
            "title": "Contradicting Count",
            "default": 0
          },
          "neutral_count": {
            "type": "integer",
            "title": "Neutral Count",
            "default": 0
          },
          "trace": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Trace"
          },
          "metadata": {
            "additionalProperties": true,
            "type": "object",
            "title": "Metadata"
          }
        },
        "type": "object",
        "required": [
          "finding_id",
          "finding_type",
          "statement",
          "confidence"
        ],
        "title": "ReviewFinding",
        "description": "A single evidence-backed finding in a review section."
      },
      "ReviewRequest": {
        "properties": {
          "review_id": {
            "type": "string",
            "title": "Review Id"
          },
          "review_type": {
            "type": "string",
            "title": "Review Type"
          },
          "title": {
            "type": "string",
            "title": "Title",
            "default": ""
          },
          "query": {
            "type": "string",
            "title": "Query",
            "default": ""
          },
          "target_entities": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Target Entities"
          },
          "target_documents": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Target Documents"
          },
          "min_confidence": {
            "type": "number",
            "maximum": 1.0,
            "minimum": 0.0,
            "title": "Min Confidence",
            "default": 0.3
          },
          "max_documents": {
            "type": "integer",
            "exclusiveMinimum": 0.0,
            "title": "Max Documents",
            "default": 10
          },
          "include_contradictions": {
            "type": "boolean",
            "title": "Include Contradictions",
            "default": true
          },
          "include_gaps": {
            "type": "boolean",
            "title": "Include Gaps",
            "default": true
          },
          "include_consensus": {
            "type": "boolean",
            "title": "Include Consensus",
            "default": true
          },
          "metadata": {
            "additionalProperties": true,
            "type": "object",
            "title": "Metadata"
          }
        },
        "type": "object",
        "required": [
          "review_id",
          "review_type"
        ],
        "title": "ReviewRequest",
        "description": "Request to generate a literature review / synthesis document."
      },
      "ReviewResult": {
        "properties": {
          "review_id": {
            "type": "string",
            "title": "Review Id"
          },
          "review_type": {
            "type": "string",
            "title": "Review Type"
          },
          "title": {
            "type": "string",
            "title": "Title"
          },
          "abstract": {
            "type": "string",
            "title": "Abstract",
            "default": ""
          },
          "sections": {
            "items": {
              "$ref": "#/components/schemas/ReviewSection"
            },
            "type": "array",
            "title": "Sections"
          },
          "findings": {
            "items": {
              "$ref": "#/components/schemas/ReviewFinding"
            },
            "type": "array",
            "title": "Findings"
          },
          "total_findings": {
            "type": "integer",
            "title": "Total Findings",
            "default": 0
          },
          "total_evidence_items": {
            "type": "integer",
            "title": "Total Evidence Items",
            "default": 0
          },
          "total_documents_cited": {
            "type": "integer",
            "title": "Total Documents Cited",
            "default": 0
          },
          "total_words": {
            "type": "integer",
            "title": "Total Words",
            "default": 0
          },
          "confidence": {
            "type": "number",
            "maximum": 1.0,
            "minimum": 0.0,
            "title": "Confidence",
            "default": 0.0
          },
          "traceability_verified": {
            "type": "boolean",
            "title": "Traceability Verified",
            "default": false
          },
          "traceability_failures": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Traceability Failures"
          },
          "warnings": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Warnings"
          },
          "errors": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Errors"
          },
          "bibliography": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Bibliography"
          },
          "source_attribution": {
            "additionalProperties": {
              "items": {
                "type": "string"
              },
              "type": "array"
            },
            "type": "object",
            "title": "Source Attribution"
          },
          "statistics": {
            "additionalProperties": true,
            "type": "object",
            "title": "Statistics"
          },
          "metadata": {
            "additionalProperties": true,
            "type": "object",
            "title": "Metadata"
          }
        },
        "type": "object",
        "required": [
          "review_id",
          "review_type",
          "title"
        ],
        "title": "ReviewResult",
        "description": "The complete output of the synthesis engine.\n\nreview_id is copied from ReviewRequest.review_id (caller-provided).\nNo timestamps, no UUIDs \u2014 deterministic by design."
      },
      "ReviewSection": {
        "properties": {
          "section_id": {
            "type": "string",
            "title": "Section Id"
          },
          "section_type": {
            "type": "string",
            "title": "Section Type"
          },
          "title": {
            "type": "string",
            "title": "Title"
          },
          "content": {
            "type": "string",
            "title": "Content",
            "default": ""
          },
          "summary": {
            "type": "string",
            "title": "Summary",
            "default": ""
          },
          "findings": {
            "items": {
              "$ref": "#/components/schemas/ReviewFinding"
            },
            "type": "array",
            "title": "Findings"
          },
          "paragraphs": {
            "items": {
              "type": "string"
            },
            "type": "array",
            "title": "Paragraphs"
          },
          "confidence": {
            "type": "number",
            "maximum": 1.0,
            "minimum": 0.0,
            "title": "Confidence",
            "default": 0.0
          },
          "word_count": {
            "type": "integer",
            "title": "Word Count",
            "default": 0
          },
          "is_mandatory": {
            "type": "boolean",
            "title": "Is Mandatory",
            "default": false
          },
          "statistics": {
            "additionalProperties": true,
            "type": "object",
            "title": "Statistics"
          },
          "metadata": {
            "additionalProperties": true,
            "type": "object",
            "title": "Metadata"
          }
        },
        "type": "object",
        "required": [
          "section_id",
          "section_type",
          "title"
        ],
        "title": "ReviewSection",
        "description": "A section of a literature review document."
      },
      "Token": {
        "properties": {
          "access_token": {
            "type": "string",
            "title": "Access Token"
          },
          "token_type": {
            "type": "string",
            "title": "Token Type"
          }
        },
        "type": "object",
        "required": [
          "access_token",
          "token_type"
        ],
        "title": "Token"
      },
      "UserLogin": {
        "properties": {
          "username": {
            "type": "string",
            "title": "Username"
          },
          "password": {
            "type": "string",
            "title": "Password"
          }
        },
        "type": "object",
        "required": [
          "username",
          "password"
        ],
        "title": "UserLogin"
      },
      "UserRegister": {
        "properties": {
          "email": {
            "type": "string",
            "format": "email",
            "title": "Email"
          },
          "username": {
            "type": "string",
            "title": "Username"
          },
          "password": {
            "type": "string",
            "title": "Password"
          }
        },
        "type": "object",
        "required": [
          "email",
          "username",
          "password"
        ],
        "title": "UserRegister"
      },
      "ValidationError": {
        "properties": {
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "type": "array",
            "title": "Location"
          },
          "msg": {
            "type": "string",
            "title": "Message"
          },
          "type": {
            "type": "string",
            "title": "Error Type"
          },
          "input": {
            "title": "Input"
          },
          "ctx": {
            "type": "object",
            "title": "Context"
          }
        },
        "type": "object",
        "required": [
          "loc",
          "msg",
          "type"
        ],
        "title": "ValidationError"
      }
    }
  }
}

``
