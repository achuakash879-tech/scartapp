from flask import Flask, render_template

app = Flask(__name__)

@app.route('/greater')
def greater(num1, num2):
        num1 = 10
        num2 = 20    
        return render_template('greater.html', i=num1, j=num2)

@app.route('/table/<int:num1>/<int:num2>')
def table(num1, num2):
    return render_template('table.html', i=num1, j=num2)

@app.route('/mark/<int:marks>')
def mark(marks):
    return render_template('mark.html', mark=marks)

@app.route('/check')
def checkValue():
    number = 10
    return render_template('check.html', number=number)
#create objects
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/about/')
def about():
    user = "Akash"  
    place = "India"
    age = 25
    city = "Mumbai"
    hobbies = ["Reading", "Swimming", "Coding"]
    return render_template('about.html', user=user, place=place, age=age, city=city, hobbies=hobbies)

@app.route('/contact')
def contact():
    return '''Hello, welcome to our contact page!<br>
              Contact us at : 111222333 <br>
             Email us at : adsfsgdk@gmail.com<br>'''

@app.route('/profile/<username>')
def profile(username):
    return f'<h1>Hello, {username}! <br>This is your profile page.</h1>'

if __name__ == '__main__':
    app.run(debug=True)