###
# Copyright (c) 2012, Ben Schomp
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import os
import re
import string
import random
import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks

## Sets: the plugin that controls gameplay ##
class Sets(callbacks.Plugin):
    """This plugin will play a version of the card game 'Sets' with
    the users. There are several levels and varieties of play..."""
    pass

    # game constants
    global NUM_CARDS, CARDS_PER_ROW
    NUM_CARDS = 12
    CARDS_PER_ROW = 4

    # level constants
    global NORMAL, HARD, MONOCHROME
    NORMAL = 'normal'
    HARD = 'hard'
    MONOCHROME = 'monochrome'

    # color constants
    global WHITE, GREEN, RED, YELLOW, LGRAY
    WHITE = '\x030'
    GREEN = '\x033'
    RED = '\x035'
    YELLOW = '\x037'
    LGRAY = '\x0315'

    def __init__( self, irc ):
        self.__parent = super( Sets, self )
        self.__parent.__init__( irc )
        self.game = None

    # start a new game of Sets
    def sets( self, irc, msg, args, channel, level ):
        """[level]

        Start a game of Sets! Level: {normal|hard|monochrome}.
        Each card has up to four 'attributes': SHAPE, NUMBER, COLOR, and
        PATTERN. Match three cards where the attributes of each
        card are either all the same, or all different: [ x ][o o][###]
        all have the same COLOR, but different SHAPES and a different NUMBER of shapes.
        Guess three card letters: sdf
        (Preceed multiple guesses with : or ,)
        """
        # start the game
        if self.gameIsRunning():
            irc.reply( "Game in progress (use '@giveup' to stop)." )
            self.game.displayAll()
        else:
            channel = ircutils.toLower(channel)
            self.game = self.Game(irc, channel, level)
            if self.gameIsRunning():
                self.game.displayBoard()
                self.game.displayRemainingCount()
            else:
                irc.reply( "A board with no Sets was dealt. Aborting..." )
    sets = wrap( sets, [ 'channel', optional( ('literal', [NORMAL, HARD, MONOCHROME] ), NORMAL ) ] )
    
    # stop the game
    def giveup( self, irc, msg, args ):
        """<no arguments>

        Stop the game and display remaining Sets."""
        if self.gameIsRunning():
            self.game.gameOver()
        else:
            irc.reply( "No game found... Use '@sets' to start one." )
    giveup = wrap( giveup )

    # request to display game states
    def show( self, irc, msg, args, option ):
        """<what to show>

        Show one of: board, scores, found, notfound, vfound, vnotfound, all.
        Options prefaced with 'v' are 'verbose' versions of that option."""
        if self.game == None:
            irc.reply( "No game found... Use '@sets' to start one." )
            return
        if option == 'board':
            self.game.displayBoard()
            self.game.displayNotFoundSets()
        elif option == 'scores':
            self.game.displayScores()
        if option == 'found':
            self.game.displayFoundSets()
        elif option == 'vfound':
            self.game.displayFoundSets( verbose=True )
        elif option == 'notfound' or option == 'remaining':
            self.game.displayNotFoundSets()
        elif option == 'vnotfound':
            self.game.displayNotFoundSets( verbose=True )
        elif option == 'all':
            self.game.displayAll()
    show = wrap( show, [ optional( ('literal',
        ['board', 'scores', 'found', 'vfound', 'remaining', 'notfound', 'vnotfound', 'all'] ), 'board' ) ] )

    # return bool if this game is running or not
    #   (if a game was never started, return False)
    def gameIsRunning( self ):
        if self.game == None:
            return False
        else:
            return self.game.isRunning

    # looks for any sets guesses (regexp for groups of 3 alphanums)
    def doPrivmsg( self, irc, msg ):
        channel = ircutils.toLower(msg.args[0])
        if not irc.isChannel(channel):
            return
        if self.gameIsRunning():
            rawGuesses = msg.args[1]
            # TODO: use 'keymap' and fail the match if anything doesn't match
            if rawGuesses[0] == ':' or rawGuesses[0] == ',':
                guesses = re.findall( r"\b([qwerasdfzxcv]{3})\b", rawGuesses )
            else:
                guesses = re.findall( r"^([qwerasdfzxcv]{3})$", rawGuesses )
            self.game.answer( guesses, msg.nick )


    ## Game: represent the game of Sets ## {{{
    class Game:
        def __init__(self, irc, channel, level):
            self.irc = irc
            self.channel = channel
            self.level = level
            self.scores = {}
            self.isRunning = False

            levelText = ''
            if level == HARD:
                levelText = ' hard'

            # start the game and init the board
            self.reply( "Starting a{0} game of Sets:".format( levelText) )
            self.board = self.Board( self.level )
            self.isRunning = True

        def reply(self, s):
            self.irc.queueMsg(ircmsgs.privmsg(self.channel, s))

        def displayBoard(self):
            displayText = self.board.displayText()
            for i in range(0, NUM_CARDS, CARDS_PER_ROW):
                self.reply( ' '.join( displayText[i:i+CARDS_PER_ROW] ) )

        def notFoundSetsCount(self):
            return len( self.board.sets )

        def notFoundSetsExist(self):
            return self.notFoundSetsCount() > 0

        def displayRemainingCount(self):
            count = self.notFoundSetsCount()
            self.reply( "There {0} {1} remaining Set{2}...".format(
                'is' if count == 1 else 'are', count, '' if count == 1 else 's') )

        def displayFoundSets(self, verbose=False):
            self.reply( "Found: " + self.board.foundSetsText(verbose) )

        def displayNotFoundSets(self, verbose=False):
            if self.isRunning:
                self.displayRemainingCount()
            else:
                self.reply( "Not Found: " + self.board.notFoundSetsText(verbose) )

        def displayScores(self):
            text = ''
            if not self.isRunning:
                text = 'Final '
            text += 'Scores: '
            if len( self.scores ) == 0:
                text += '-none-'
            else:
                scoresText = []
                for name, score in self.scores.iteritems():
                    scoresText.append( name + self.formatPoints(score) )
                text += '. '.join( scoresText ) + '.'

            self.reply( text )

        def displayAll(self):
            self.displayBoard()
            self.displayNotFoundSets()
            self.displayFoundSets()
            self.displayScores()

        # stops the game
        def gameOver(self):
            self.isRunning = False
            self.reply( "-- Game Over --" )
            if self.notFoundSetsExist():
                self.displayNotFoundSets( verbose = self.notFoundSetsCount() <= 3 )
            self.displayScores()

        # return color str with leading space, optional + and trailing LGRAY
        #  ie: 7 becomes GREEN ' 7' and -2 becomes RED ' -2'
        def formatPoints(self, points, plus=False):
            sign = ''
            if points< 0:
                color = RED
            elif points == 0:
                color = YELLOW
            else:
                color = GREEN
                if plus:
                    sign = '+'
            return color + ' ' + sign + str(points) + LGRAY

        # builds the response to a player's guess
        def answerResponse(self, name, found, missed, dups, invalid, scoreDelta, score):
            remainingText = ''
            itemizedText = []
            if found:
                notFound = self.notFoundSetsCount()
                itemizedText.append( self.board.setsText( found, verbose=True ) )
                if notFound > 0:
                    setText = ' Set'
                    if notFound != 1:
                        setText += 's'
                    remainingText = " (" + str(notFound) + setText + " remaining)"

            if missed:
                itemizedText.append( str(missed) + " wrong" )

            if dups:
                itemizedText.append( "{0} dup{1}".format( dups, '' if dups == 1 else 's' ) )

            if invalid:
                itemizedText.append( str(invalid) + " invalid" )

            pointsText = "{0} point{1}".format(
                    self.formatPoints( scoreDelta, plus=True ), '' if scoreDelta == 1 else 's' )

            return LGRAY + "{0}: {1} for{2},{3} total.{4}".format(
                    name, ', '.join(itemizedText), pointsText, self.formatPoints( score ), remainingText )

        # check guesses for sets
        def answer(self, guesses, name ):
            if guesses:
                ( found, missed, dups, invalid, scoreDelta ) = self.board.checkAnswer( guesses )

                if not name in self.scores:
                    self.scores[name] = 0
                self.scores[name] += scoreDelta
                self.reply( self.answerResponse( name, found, missed, dups, invalid, scoreDelta, self.scores[name] ) )

                if found and not self.notFoundSetsExist():
                    self.gameOver()


        ## Board: represent the playing board which contains Cards does all calulations ## {{{
        class Board:
            def __init__(self, level):
                self.level = level
                self.sets = []
                self.foundSets = []
                self.keymap = [ 'q','w','e','r',
                                'a','s','d','f',
                                'z','x','c','v' ]

                # draw cards and find all sets
                while not self.sets:
                    self.cards = []
                    for i in range(NUM_CARDS):
                        while True:
                            c = self.Card(self.level)
                            try:
                                self.cards.index( c )
                                # c is a duplicate, keep trying
                            except:
                                break;
                        self.cards.append( c )
                    self.sets = self.findSets()

                self.setCount = 0
                self.totalNumSets = len(self.sets)

            # returns a list of tuples that represents all the Sets in the Board.
            def findSets(self):
                result = []
                for i in range( 0, NUM_CARDS-2 ):
                    for j in range( i+1, NUM_CARDS-1 ):
                        for k in range( j+1, NUM_CARDS ):
                            if self.isASet( self.cards[i], self.cards[j], self.cards[k] ):
                                # sort the set for consistent lookup
                                result.append( ''.join(
                                    sorted( [ self.keymap[i], self.keymap[j], self.keymap[k] ] ) ) )
                return result

            # scans the guesses for sets and returns the score for these guesses
            #  (the number correct is the size of the good list)
            def checkAnswer(self, guesses):
                good = []
                bad = dup = invalid = scoreDelta = 0
                for guess in guesses:
                    # sets are sorted when they're stored
                    sortedGuess = ''.join( sorted( guess ) )
                    if sortedGuess[0] == sortedGuess[1] or sortedGuess[1] == sortedGuess[2]:
                        invalid += 1
                        continue
                    try:
                        self.sets.remove( sortedGuess )
                        self.foundSets.append( sortedGuess )
                        good.append( guess )
                        self.setCount += 1
                        scoreDelta += int( round( ( (self.setCount*2.5) / self.totalNumSets ) +
                                           ((self.setCount==self.totalNumSets)/2) ) + 1 )
                    except:
                        # not in the notFound sets
                        try:
                            self.foundSets.index( sortedGuess )
                            dup += 1
                            scoreDelta += 0
                        except:
                            # not in the found sets either
                            bad += 1
                            scoreDelta -= 2
                return (good, bad, dup, invalid, scoreDelta)

            # returns a list of the Board's display text (one Card per element)
            def displayText(self):
                displayText = [];
                for (card,key) in zip(self.cards,self.keymap):
                    displayText.append( key + ':' + card.displayText() )
                return displayText 

            # helper for (un)foundSetsText
            # verbose: bool for keymaps only, or verbose card
            def setsText(self, sets, verbose):
                if len( sets ) == 0:
                    return '-none-'

                if verbose:
                    verboseText = []
                    for s in sets:
                        verboseText.append( '{0}{1}{2}[{3}|{4}|{5}]'.format(
                            s[0], s[1], s[2],
                            self.cards[self.keymap.index(s[0])].displayText(minimal=True), 
                            self.cards[self.keymap.index(s[1])].displayText(minimal=True),
                            self.cards[self.keymap.index(s[2])].displayText(minimal=True) ) )
                    text = ', '.join( verboseText )
                else:
                    text = ', '.join( sets )
                return text

            # returns a textual representation of the notFound Sets
            def notFoundSetsText(self, verbose=False):
                return self.setsText( self.sets, verbose )

            # returns a textual representation of the found Sets
            def foundSetsText(self, verbose=False):
                return self.setsText( self.foundSets, verbose )

            # helper for isASet
            def allSameOrDifferent(self, a, b, c):
                return (a==b and b==c and a==c) or (a!=b and b!=c and a!=c)

            # returns true if the three card parameters make a 'Set'
            #  (all properties of each card are either all the same, or all different)
            def isASet(self, card1, card2, card3):
                result = self.allSameOrDifferent(card1.shape, card2.shape, card3.shape)
                result &= self.allSameOrDifferent(card1.number, card2.number, card3.number)
                if not result: # we failed shape/number checks
                    return result

                result = self.allSameOrDifferent(card1.color, card2.color, card3.color)
                if self.level == NORMAL or not result: # normal or we failed color check
                    return result

                result = self.allSameOrDifferent(card1.pattern, card2.pattern, card3.pattern)
                return result

            ## Card: represent a single card ## {{{
            class Card:
                PLAIN = ''
                ULINE = '\x1f'
                REVERSE = '\x16'
                RESET = '\x0f'

                # one card: shape, number, color, and pattern
                def __init__(self, level):
                    self.rng = random.Random()
                    self.rng.seed()
                    self.shape = self.rng.choice( ['x', 'o', '#'] )
                    self.number = self.rng.randint(1,3)

                    if level == MONOCHROME:
                        self.color = LGRAY
                    else:
                        self.color = self.rng.choice( [RED, GREEN, YELLOW ] )

                    if level == HARD or level == MONOCHROME:
                        self.pattern = self.rng.choice( [self.PLAIN, self.ULINE, self.REVERSE] )
                    else:
                        self.pattern = self.PLAIN

                def __ne__(self, other):
                    return (self.shape != other.shape or
                        self.number != other.number or
                        self.color != other.color or
                        self.pattern != other.pattern)

                def __eq__(self, other):
                    return not self.__ne__(other)


                # returns a textual representation of the card
                #   (contains irc color control characters)
                def displayText(self, minimal=False):
                    if minimal:
                        return self.pattern + self.color + (self.shape * self.number) + self.RESET
                    else: 
                        s = '[' + self.pattern + self.color;
                        if self.number == 1:
                            s += ' ' + self.shape + ' ';
                        elif self.number == 2:
                            s += self.shape + ' ' + self.shape;
                        else:
                            s += self.shape * 3
                        s += self.RESET + ']'
                        return s

            # }}} end Card

        # }}} end Board

    # }}} end Game
    
# end Sets

Class = Sets


# vim:set shiftwidth=4 softtabstop=4 expandtab
