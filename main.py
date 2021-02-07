from contest import client

if __name__ == "__main__":
    bot = client.ContestClient()

    with open('token.dat', 'r') as file:
        bot.run(file.read())
