#!/bin/bash
# Ollama proxy that routes all requests to AX650 backend
# This allows your existing code to work unchanged

set -e

OLLAMA_PORT="${OLLAMA_PORT:-11434}"
BACKEND_URL="${AX650_BACKEND_URL:-http://localhost:5002}"

echo "Starting Ollama AX650 Proxy on port $OLLAMA_PORT"
echo "Backend: $BACKEND_URL"

# Simple proxy using Python
python3 << 'PYTHON_SCRIPT'
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import os

BACKEND_URL = os.getenv('AX650_BACKEND_URL', 'http://localhost:5002')
OLLAMA_PORT = int(os.getenv('OLLAMA_PORT', '11434'))

class OllamaProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Ollama AX650 Proxy is running')
        elif self.path == '/api/tags':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "models": [{
                    "name": "qwen3-ax650:latest",
                    "model": "qwen3-ax650:latest",
                    "modified_at": "2025-11-24T00:00:00Z",
                    "size": 5100000000,
                    "digest": "ax650:qwen3-4b",
                    "details": {
                        "parent_model": "",
                        "format": "axmodel",
                        "family": "qwen3",
                        "families": ["qwen3"],
                        "parameter_size": "4B",
                        "quantization_level": "INT8"
                    }
                }]
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body.decode('utf-8'))
        except:
            self.send_error(400, 'Invalid JSON')
            return
        
        if self.path == '/api/generate':
            # Convert Ollama format to backend format
            prompt = data.get('prompt', '')
            options = data.get('options', {})
            stream = data.get('stream', False)
            
            backend_request = {
                'prompt': prompt,
                'max_tokens': options.get('num_predict', 128),
                'temperature': options.get('temperature', 0.8),
                'top_p': options.get('top_p', 0.9),
                'top_k': options.get('top_k', 40)
            }
            
            try:
                # Call backend
                response = requests.post(
                    f'{BACKEND_URL}/generate',
                    json=backend_request,
                    timeout=3600
                )
                response.raise_for_status()
                result = response.json()
                
                # Convert backend response to Ollama format
                if stream:
                    # For streaming, send chunks
                    self.send_response(200)
                    self.send_header('Content-type', 'application/x-ndjson')
                    self.end_headers()
                    
                    # Send the complete response as one chunk
                    chunk = {
                        'model': data.get('model', 'qwen3-ax650'),
                        'created_at': '2025-11-24T00:00:00Z',
                        'response': result.get('text', ''),
                        'done': True
                    }
                    self.wfile.write((json.dumps(chunk) + '\n').encode())
                else:
                    # Non-streaming response
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    ollama_response = {
                        'model': data.get('model', 'qwen3-ax650'),
                        'created_at': '2025-11-24T00:00:00Z',
                        'response': result.get('text', ''),
                        'done': True,
                        'context': [],
                        'total_duration': 0,
                        'load_duration': 0,
                        'prompt_eval_count': 0,
                        'prompt_eval_duration': 0,
                        'eval_count': len(result.get('text', '').split()),
                        'eval_duration': 0
                    }
                    self.wfile.write(json.dumps(ollama_response).encode())
                    
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'error': str(e)}
                self.wfile.write(json.dumps(error_response).encode())
                
        elif self.path == '/api/chat':
            # Convert chat format to simple generate
            messages = data.get('messages', [])
            # Combine messages into a single prompt
            prompt = '\n'.join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages])
            
            options = data.get('options', {})
            stream = data.get('stream', False)
            
            backend_request = {
                'prompt': prompt,
                'max_tokens': options.get('num_predict', 128),
                'temperature': options.get('temperature', 0.8),
                'top_p': options.get('top_p', 0.9),
                'top_k': options.get('top_k', 40)
            }
            
            try:
                response = requests.post(
                    f'{BACKEND_URL}/generate',
                    json=backend_request,
                    timeout=3600
                )
                response.raise_for_status()
                result = response.json()
                
                # Convert to Ollama chat format
                if stream:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/x-ndjson')
                    self.end_headers()
                    
                    chunk = {
                        'model': data.get('model', 'qwen3-ax650'),
                        'created_at': '2025-11-24T00:00:00Z',
                        'message': {
                            'role': 'assistant',
                            'content': result.get('text', '')
                        },
                        'done': True
                    }
                    self.wfile.write((json.dumps(chunk) + '\n').encode())
                else:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    ollama_response = {
                        'model': data.get('model', 'qwen3-ax650'),
                        'created_at': '2025-11-24T00:00:00Z',
                        'message': {
                            'role': 'assistant',
                            'content': result.get('text', '')
                        },
                        'done': True
                    }
                    self.wfile.write(json.dumps(ollama_response).encode())
                    
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'error': str(e)}
                self.wfile.write(json.dumps(error_response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{self.address_string()}] {format % args}")

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', OLLAMA_PORT), OllamaProxyHandler)
    print(f'Ollama AX650 Proxy listening on port {OLLAMA_PORT}')
    print(f'Backend URL: {BACKEND_URL}')
    print('Ready to receive requests...')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.shutdown()
PYTHON_SCRIPT
