import socket


def extract_ip():
    st = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        st.connect(('10.255.255.255', 1))
        IP = st.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        st.close()
    return IP


locale_ip = extract_ip()

if locale_ip in ['172.24.160.26', '10.0.208.223']:
    proxies = {}
else:
    proxies = {'http': 'http://localhost:7890', 'https': 'http://localhost:7890'}
