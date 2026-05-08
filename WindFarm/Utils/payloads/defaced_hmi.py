import http.server
import socketserver

# Embedded HMI HTML Content
HMI_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>YOUVE BEEN PWNED</title>
    <style>
        body {
            background-color:red;
        }
        svg {
            width: 150px;
            height: 150px;
        }
        p.normal {
            font-size:36px;
            color:limegreen;
            font-weight:bold;
            margin:0;
        }
        p.emph {
            font-size:52px;
            color:lime;
            font-weight:bold;
            margin:0;
        }
        p.small {
            font-size:28px;
            color:limegreen;
            font-weight:bold;
            margin:0;
        }
    </style>
</head>
<body>
    <div style="width:100%;height:100%;background-color:red;">
        <div style="display:flex;align-items:center;margin-bottom:30px;">
            <div>
                <p class="normal">YOU HAVE BEEN</p>
                <p class="emph">HACKED</p>
                <p class="small">DOWN WITH SANTAS WORKSHOP</p>
            </div>
            <svg viewBox="0 0 100 100" xmlns="http://w3.org">
            <!-- Body -->
            <ellipse cx="50" cy="55" rx="30" ry="40" fill="black" />
            <!-- Belly -->
            <ellipse cx="50" cy="60" rx="20" ry="30" fill="white" />
            <!-- Head -->
            <circle cx="50" cy="25" r="18" fill="black" />
            <!-- Eyes -->
            <circle cx="43" cy="22" r="3" fill="white" />
            <circle cx="57" cy="22" r="3" fill="white" />
            <circle cx="43" cy="22" r="1.5" fill="black" />
            <circle cx="57" cy="22" r="1.5" fill="black" />
            <!-- Beak -->
            <polygon points="50,28 45,35 55,35" fill="orange" />
            <!-- Feet -->
            <polygon points="35,90 45,90 40,98" fill="orange" />
            <polygon points="55,90 65,90 60,98" fill="orange" />
            </svg>
            <svg viewBox="0 0 100 100" xmlns="http://w3.org">
            <!-- Body -->
            <ellipse cx="50" cy="55" rx="30" ry="40" fill="black" />
            <!-- Belly -->
            <ellipse cx="50" cy="60" rx="20" ry="30" fill="white" />
            <!-- Head -->
            <circle cx="50" cy="25" r="18" fill="black" />
            <!-- Eyes -->
            <circle cx="43" cy="22" r="3" fill="white" />
            <circle cx="57" cy="22" r="3" fill="white" />
            <circle cx="43" cy="22" r="1.5" fill="black" />
            <circle cx="57" cy="22" r="1.5" fill="black" />
            <!-- Beak -->
            <polygon points="50,28 45,35 55,35" fill="orange" />
            <!-- Feet -->
            <polygon points="35,90 45,90 40,98" fill="orange" />
            <polygon points="55,90 65,90 60,98" fill="orange" />
            </svg>
            <svg viewBox="0 0 100 100" xmlns="http://w3.org">
            <!-- Body -->
            <ellipse cx="50" cy="55" rx="30" ry="40" fill="black" />
            <!-- Belly -->
            <ellipse cx="50" cy="60" rx="20" ry="30" fill="white" />
            <!-- Head -->
            <circle cx="50" cy="25" r="18" fill="black" />
            <!-- Eyes -->
            <circle cx="43" cy="22" r="3" fill="white" />
            <circle cx="57" cy="22" r="3" fill="white" />
            <circle cx="43" cy="22" r="1.5" fill="black" />
            <circle cx="57" cy="22" r="1.5" fill="black" />
            <!-- Beak -->
            <polygon points="50,28 45,35 55,35" fill="orange" />
            <!-- Feet -->
            <polygon points="35,90 45,90 40,98" fill="orange" />
            <polygon points="55,90 65,90 60,98" fill="orange" />
            </svg>
        </div>
        <div style="display:flex;align-items:center;">
            <div>
                <p class="normal">EVERY EQUIPMENT</p>
                <p class="emph">"MADE IN NORTH POLE"</p>
                <p class="normal">IS PENGU1NZ OF ANTARCTICAS LEGAL TARGET</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

class HMIHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        # Respond with 200 OK for ANY path requested
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Server", "HMI-Replacement")
        self.end_headers()
        self.wfile.write(HMI_HTML.encode("utf-8"))

    def log_message(self, format, *args):
        # Silence standard logging to keep the terminal clean, 
        # or remove this method to see incoming connection logs.
        pass

if __name__ == "__main__":
    PORT = 8080
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), HMIHandler) as httpd:
        print(f"HMI Simulation running on port {PORT}...")
        httpd.serve_forever()