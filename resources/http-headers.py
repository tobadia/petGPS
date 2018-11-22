from flask import Flask, request

app = Flask(__name__)

@app.route('/')
def main():
    print(request.headers)
    #print(request.headers['User-Agent'])
    return('This is the root of the web server')

@app.route('/hello')
def hello():
    return('Hello, world!')

if __name__ == '__main__':
    app.run()
