PRINT_WIDTH = 80


def choose_option(
        options,
        title='Key in the number corresponding to the action you wish to take.'
):
    line = '-=x=' * 20 + '-'
    title = '\n'.join(
        [sub_title.center(PRINT_WIDTH) for sub_title in title.split('\n')]
    )
    options_len = len(options)
    print(line)
    print(title)
    print(line)
    for ind, option in enumerate(options):
        print(f'({ind}): {option}')
    print()
    print('Press q to quit')
    print()
    choice = input('CHOICE: ')
    print()
    if choice == 'q':
        print('Exiting program')
        exit(0)
    if choice.isnumeric():
        choice = int(choice)
        if 0 <= choice < options_len:
            return options[choice]
        else:
            print('ERROR: Number entered not within range.')
            return choose_option(options)
    else:
        print('ERROR: Only numeric characters allowed.')
        return choose_option(options)


