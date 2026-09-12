"""Start the movie browser on localhost:3002 and open the default browser."""
import argparse
import json
import threading
import urllib.request
import webbrowser

from server import ROOT, Handler, ThreadingHTTPServer

URL = 'http://localhost:3002/'

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true', help='Start without opening a browser')
    options = parser.parse_args()
    try:
        server = ThreadingHTTPServer(('127.0.0.1', 3002), Handler)
    except OSError as error:
        # Reuse our existing server; never stop another application on this port.
        try:
            with urllib.request.urlopen('http://127.0.0.1:3002/api/meta', timeout=3) as response:
                meta = json.load(response)
            assert {'primaryTitle', 'numVotes', 'tconst'} <= {c['key'] for c in meta['columns']}
        except Exception:
            raise SystemExit(f'Could not start the movie browser on port 3002: {error}')
        print(f'Movie browser is already running: {URL}', flush=True)
        if not options.no_browser:
            webbrowser.open(URL)
        return
    try:
        if not (ROOT / 'movies.sqlite3').exists():
            from import_data import build
            build()
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        print(f'Movie browser: {URL}\nKeep this window open. Press Control+C to stop.', flush=True)
        if not options.no_browser:
            webbrowser.open(URL)
        try:
            worker.join()
        except KeyboardInterrupt:
            server.shutdown()
            worker.join()
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
