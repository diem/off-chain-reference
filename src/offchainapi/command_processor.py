class CommandProcessor:

    def business_context(self):
        ''' Provides the business context associated with this processor. '''
        pass

    def check_command(self, vasp, channel, executor, command):
        ''' Checks a command in the full context to see if it is acceptable or not. '''
        pass

    def process_command(self, vasp, channel, executor, command, status, error=None):
        ''' Processes a command. '''
        pass
