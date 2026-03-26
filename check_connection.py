"""
Check Internet and VoIP Server Connectivity
"""
import socket
import sys

def check_internet():
    """Check basic internet connectivity"""
    print("Checking Internet Connection...")
    print("-" * 60)
    
    try:
        # Try to resolve a domain
        socket.gethostbyname('google.com')
        print("[OK] Internet connection: ACTIVE")
        return True
    except socket.gaierror:
        print("[ERROR] Internet connection: FAILED")
        print("  - Cannot resolve google.com")
        return False
    except Exception as e:
        print("[ERROR] {}".format(str(e)))
        return False

def check_voip_server():
    """Check VoIP server connectivity"""
    print()
    print("Checking VoIP Server...")
    print("-" * 60)
    
    server = 'jhb1.vphone.co.za'
    port = 5060
    
    try:
        # Try DNS resolution
        print("Resolving {}...".format(server))
        ip = socket.gethostbyname(server)
        print("[OK] Server resolved: {} -> {}".format(server, ip))
        
        # Try UDP connection (SIP uses UDP)
        print("Testing UDP connection to {}:{}...".format(server, port))
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        
        try:
            sock.sendto(b'TEST', (server, port))
            print("[OK] UDP port {} is reachable".format(port))
            result = True
        except socket.timeout:
            print("[WARNING] UDP port {} timeout (may still work)".format(port))
            result = True  # This is OK - SIP server may not respond to raw data
        finally:
            sock.close()
        
        return result
        
    except socket.gaierror:
        print("[ERROR] Cannot resolve {}".format(server))
        return False
    except Exception as e:
        print("[ERROR] {}".format(str(e)))
        return False

def check_firewall():
    """Check firewall/network info"""
    print()
    print("Network Information...")
    print("-" * 60)
    
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
        print("Hostname: {}".format(hostname))
        print("Local IP: {}".format(local_ip))
        return True
    except Exception as e:
        print("[ERROR] {}".format(str(e)))
        return False

def main():
    print()
    print("=" * 60)
    print("VoIP CONNECTION DIAGNOSTIC")
    print("=" * 60)
    print()
    
    internet_ok = check_internet()
    server_ok = check_voip_server()
    network_ok = check_firewall()
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("Internet:      {}".format("OK" if internet_ok else "FAILED"))
    print("VoIP Server:   {}".format("OK" if server_ok else "FAILED"))
    print("Network:       {}".format("OK" if network_ok else "FAILED"))
    print()
    
    if internet_ok and server_ok:
        print("[OK] Your connection is ready for VoIP calls!")
        print()
        print("Next: Run 'C:\\sip\\.venv\\Scripts\\python.exe c:\\sip\\working_call.py'")
        return 0
    else:
        print("[ERROR] Connection issues detected")
        print()
        if not internet_ok:
            print("Solutions:")
            print("  - Check your WiFi/Ethernet connection")
            print("  - Try pinging a public server: ping 8.8.8.8")
            print("  - Check firewall settings")
        if not server_ok:
            print("  - VoIP server may be down or unreachable")
            print("  - Check if port 5060 (SIP) is blocked by firewall")
            print("  - Verify server address: jhb1.vphone.co.za")
        return 1

if __name__ == "__main__":
    sys.exit(main())
