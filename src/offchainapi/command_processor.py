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

    def process_command_backlog(self, vasp):
        ''' Sends commands that have been resumed after being interrupted to other
            VASPs.'''
        pass

    def notify(self):
        '''Call this function to notify that a new command is available,
           after an interruption'''
        pass
