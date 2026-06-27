from flask import Flask, render_template

app = Flask(__name__)
@app.route('/')
def home():
    return render_template('collegebase.html')


@app.route('/index')
def index():
    return render_template('index.html') 
@app.route('/student/<name>')
def student(name):
    return f'<h1>Hello, {name}! <br>Welcome to our college.</h1>'

@app.route('/about')
def about():
    return render_template('about.html')
@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/departments')
def departments():
    depts = 'Computer Science, Electronics, Mechanical, Civil, Electrical'
    return render_template('departments.html', depts=depts )

if __name__ == '__main__':
    app.run(debug=True)