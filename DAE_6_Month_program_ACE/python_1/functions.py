# Function without paremeters
def greet_user():
    print("-------------------------")
    print("Say, username")
    print("hope you have a nice day")
    print("-------------------------")

# Function with a paremeter
    def greet_user(username, hometown):
    print("-------------------------")
    print(username, hometown)
    print("-------------------------")

# Calling a function without an argument
name = input("What's your name: ")
hometown = input("what's your hometown: ")
# Calling a function with an argument
greet_user(name, hometown)
greet_user(name, hometown)
greet_user(name, hometown)
greet_user(name, hometown)
greet_user(name, hometown)

# Calling a function without an argument
# greet_user()