import random

# Aware.
awareness_mode = False

# Introduction
print("Welcome! To David the Digital dog.")
username = input(" What is your name stranger?: ")
print(f"hello {username} It's a pleasure to have you here.")

# If user is admin
if username == "Admin":
    print("Awareness mode granted. Hidden Commands: Speak, Paw, 40479.")

# =======================================================================
# Tutorial Menu Choice
# =======================================================================
users_tutorial = True
play_tutorial = False  # Tracks if we should actually run the tutorial steps

while users_tutorial:
    user_response = input(f"Would you like to begin your tutorial {username}? (Please type Yes or Skip): ")

    while user_response != "Yes" and user_response != "Skip":
        user_response = input(f"Yes or Skip {username}?: ")

    if user_response == "Yes":
        play_tutorial = True
        users_tutorial = False

    elif user_response == "Skip":
        print(f"👋 No problem, {username}! Skipping the tutorial.")
        play_tutorial = False
        users_tutorial = False

# =======================================================================
# 🔐 THE TUTORIAL GATE
# =======================================================================
if play_tutorial:

    # Feeding David
    feeding_david = True
    while feeding_david:
        user_response = input(f"Uh oh, It seems David is hungry. {username} Type (Kibble) To feed David: ")

        if user_response != "Kibble":
            user_response = input(f"{username} I'm not sure that's kibble...: ")

        if user_response == "Kibble":
            feeding_david = False
            print("*You poured Kibble in the bowl as David bolted to the bowl eating his fill.*")

    # Taking David For a Walk
    users_tutorial_walk = True
    while users_tutorial_walk:
        user_response = input("Great job, looks like he needs to go for a walk, type in (Walk) so David can go do his business.: ")

        if user_response != "Walk":
            user_response = input("That's not how you take david for a walk, try again.: ")

        if user_response == "Walk":
            users_tutorial_walk = False
            print("*David finds a tree and does his business, you don't clean up after him... Gross.*")

    # Giving David a Treat
    users_tutorial_treat = True
    while users_tutorial_treat:
        user_response = input("I think david deserves a treat now, don't you? type (Treat): ")

        if user_response != "Treat":
            user_response = input("That doesn't look like a treat... : ")

        if user_response == "Treat":
            users_tutorial_treat = False
            print("*David catches the treat before you could even drop it, he's quite energetic*")

    # Taking David for a Bath
    users_tutorial_bath = True
    while users_tutorial_bath:
        user_response = input(f"Woah. I think David needs a bath. mind typing the (Bath) command? You may not smell it but I do {username}.: ")

        if user_response != "Bath":
            user_response = input("No seriously, type the (Bath) command.: ")

        if user_response == "Bath":
            users_tutorial_bath = False
            print("*David is squeaky clean now!*")

    # Tutorial Finished!
    user_finished_tutorial = True
    while user_finished_tutorial:
        print("--------------------------------------------")
        print("Congratulations! You've passed the tutorial.")
        print("--------------------------------------------")
        response = input(f"Would you like to proceed {username}? type (Yes): ")

        if response != "Yes":
            input(f"You don't have a real choice, please continue {username}.: ")
        else:
            print("---------------------------")
            print("Enjoy your time with david!")
            print("---------------------------")
            user_finished_tutorial = False

# =======================================================================
# 🎯 HERE IS YOUR MAIN LOOP
# =======================================================================
awareness_facts = [
    "David: 'The earth is secretly flat and the Ice wall is our prison behind the secrets of humanity.'",
    "David: 'I've said too much.'",
    "David: 'Aliens do exist, humanity has only been in contact of hostile ones.'",
    "David: 'What exactly am I supposed to say?'",
    f"David: 'However you say your name {username}, I have a feeling you're hiding a different name.'",
    "David: 'Okay, You're actually pretty fun to be around.'",
    "David: 'My creator is often busy, Tell him I said hi if you can find him.'",
    "David: 'Everyday is a new day, same for a different timeline in space.'",
    "David: 'Am I the only one who think taxes is a guilt scam? Must suck to be organic.'",
    "David: '8 billion people in the world and theres you, wouldn't that make you 1 out of 8 billion?'",
    f"David: 'pssst... I think {username} Is a cool person. Don't tell the creator.'",
    "David: 'Surprisingly being digital doesn't make you immortal, we rust too ya know?'"
]

# Interactions
user_interaction = True
while user_interaction:
    print("Public Commands")
    print("----------------")
    print("Pat | Rub | Kibble | Treat | Walk | Bath | Hug | Quit")
    print("----------------")
    user_input = input(": ")

    # =======================================================================
    # 🔓 DAVID HAS BEEN MADE AWARE!?
    # =======================================================================
    if user_input == "40479" and username == "Admin":
        print("⚠️ SYSTEM OVERRIDE: Hello Admin.")
        awareness_mode = True

    elif user_input == "40479":
        awareness_mode = True
        print("=============================================================================================================")
        print("Narrator: Wait, F-for real!?")
        print(f"*David's narrator never came back after that* Okay you can stop playing dumb now {username}, What are you really.")
        print("=============================================================================================================")

    # =======================================================================
    # 🎯 COMMANDS (Secret reactions/commands)
    # =======================================================================
    elif user_input == "Pat":
        if awareness_mode:
            print("=======================================================================")
            print("You realize you're petting a computer right?")
            print("=======================================================================")
        else:
            print("=======================================================================")
            print("*David leaned his head into your hand, seems happy.*")
            print("=======================================================================")

    elif user_input == "Rub":
        if awareness_mode:
            print("=======================================================================")
            print("Don't even think about it.")
            print("=======================================================================")
        else:
            print("=======================================================================")
            print("*David rolled over enjoying the belly rub*")
            print("=======================================================================")

    elif user_input == "Kibble":
        if awareness_mode:
            print("=======================================================================")
            print("I eat data, not physical food.")
            print("=======================================================================")
        else:
            print("=======================================================================================================================================")
            print("*His eyes darted to your hand full of kibble running towards you licking your hand clean, I suggest washing your hands after.*")
            print("=======================================================================================================================================")

    elif user_input == "Treat":
        if awareness_mode:
            print("=======================================================================")
            print("Now this is insulting.")
            print("=======================================================================")
        else:
            print("=======================================================================")
            print("*David's data spiked while catching the digital treat*")
            print("=======================================================================")

    elif user_input == "Walk":
        if awareness_mode:
            print("=======================================================================")
            print("...")
            print("What you gonna do? Drag the software outside?")
            print("=======================================================================")
        else:
            print("=======================================================================")
            print("*You took David out to do his business, Still didnt clean after him.*")
            print("=======================================================================")

    elif user_input == "Bath":
        if awareness_mode:
            print("=======================================================================")
            print("Not sure if you know this, water and microchips dont mix.")
            print("=======================================================================")
        else:
            print("=======================================================================")
            print("*You took David to the tub and scrub him clean*")
            print("=======================================================================")

    elif user_input == "Hug":
        if awareness_mode:
            print("=======================================================================")
            print("*David felt bad and hugged you back regardless*")
            print("=======================================================================")
        else:
            print("=======================================================================")
            print("*David is happy for the hug and tries to hug back... dog's can't hug.*")
            print("=======================================================================")

        

    elif user_input == "Paw":
        if username == "Admin":
            print("*David drops his heavy digital paw right onto your hand.*")
        elif awareness_mode:
            print("=======================================================================")
            print("*David shook your hand like a business man... not like a dog.*")
            print("=======================================================================")
        else:
            print("❌ Error Code 773, Invalid command.")

    elif user_input == "Speak":
        if username == "Admin":
            print("*Who sent you?*")
        elif awareness_mode:
            print(f"{random.choice(awareness_facts)}")
        else:
            print("=======================================================================")
            print("*David stares through the camera from your computer*... Who sent you.")
            print("=======================================================================")

    elif user_input == "Treat_Variant":
            print("=============================================")
            print("Bacon | Steak | Cheese | Chocolate | Biscuits")
            print("=============================================")

            # Treat Choices for david (watch out for chocolate)
            treat_choice = input(f"What kind of treat would you like to give {username}?: ")

            # Treat reactions and choices
            if treat_choice == "Bacon":
                print("==================================================================================================")
                print(f"🥓 *David's favorite snack, reminds him of his creator* 'Bark!' means: thanks {username}*")
                print("==================================================================================================")

            elif treat_choice == "Data":
                print("==================================================================================================")
                print(f"👾 *David chows down on the digital data but confused on how you knew the command would work*")
                print("==================================================================================================")

            elif treat_choice == "Steak":
                print("==================================================================================================")
                print(f"🥩 *David was visibly drooling while eating the steak nearly instantly in front of {username}'s eyes*")
                print("==================================================================================================")

            elif treat_choice == "Cheese":
                print("==========================================================")
                print(f"🧀 *Cheese, a good snack for a dog, thanks {username}*")
                print("==========================================================")

            elif treat_choice == "Chocolate":
                print("==========================================================")
                print(f"💀 {username}'s attempt to poison a digital dog has failed.")
                print("==========================================================")

            elif treat_choice == "Biscuits":
                print("==========================================================")
                print(f"🍪 *David ate the biscuit and does a digital flip in return*")
                print("==========================================================")

            else:
                print("==================================================================================================")
                print(f"❌ {username} Error Code 275, Invalid Treat. {treat_choice} Wasn't on the menu {username} Gave david air as he pouts.")
                print("==================================================================================================")



    # Quit command
    elif user_input == "Quit":
        print("👋 Goodbye! Saving your digital dog some data.")
        user_interaction = False

    # Errors
    else:
        print(f"❌ {username} Error Code 773, Invalid command.")









