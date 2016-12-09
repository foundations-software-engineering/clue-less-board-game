from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

import logging
import random

logger = logging.getLogger(__name__)

"""
Implementation of status enum as a Django IntergerField of choices
"""
NOT_STARTED = 0
STARTED = 1
COMPLETE = 2
STATUS_CHOICES = (
    (NOT_STARTED, 'Not Started'),
    (STARTED, 'Started'),
    (COMPLETE, 'Complete'),
)

LOST = -1
NEITHER = 0
WON = 1
GAME_RESULT_CHOICES = (
    (LOST, "Lost"),
    (NEITHER, "Neither"),
    (WON, "Won")
)

class Board(models.Model):
    """
    Board object for the entire game.  Should be referenced by multiple games and space collections
    """
    pass


class SpaceCollection(models.Model):
    """
    Any implementations should occupy a set of spaces on the board
    """
    board = models.ForeignKey(Board)


class Space(models.Model):
    """
    Represents a space on the game board, with an X Y position and all neighbor spaces
    """
    posX = models.IntegerField()
    posY = models.IntegerField()
    spaceNorth = models.OneToOneField('self', related_name='spaceSouth', blank=True, null=True)
    spaceWest = models.OneToOneField('self', related_name='spaceEast', blank=True, null=True)
    spaceCollector = models.ForeignKey(SpaceCollection)

    def __str__(self):
        return("({},{})".format(self.posX, self.posY))


class Player(models.Model):
    """
    Represents a player in the context of a clueless game.  Ties back to Django user
    """
    user = models.ForeignKey(User, blank=True, null=True)  # only should be null for non-user players
    nonUserPlayer = models.BooleanField(default=False)
    currentSpace = models.ForeignKey(Space)
    currentGame = models.ForeignKey('Game', blank=True, null=True) # game not defined yet, using string as lazy lookup
    character = models.ForeignKey('Character', blank=True)
    gameResult = models.IntegerField(choices=GAME_RESULT_CHOICES, default=0)

    def __str__(self):
        if self.user is None:
            return ("user: {}, currentSpace: {}, currentGame: {}, character: {}".format(
                "No User", self.currentSpace.__str__(), self.currentGame.__str__(), self.character.__str__()
            ))
        else:
            return("user: {}, currentSpace: {}, currentGame: {}, character: {}".format(
                self.user.__str__(), self.currentSpace.__str__(), self.currentGame.__str__(), self.character.__str__()
            ))

    def compare(self, otherPlayer):
        return self.user == otherPlayer.user

    def getDetectiveSheet(self):
        """

        :return: The player's detective sheet for the current game
        """
        return DetectiveSheet.objects.get(game = self.currentGame, player = self)


class Hallway(SpaceCollection):
    """
    Hallway in the game
    """
    pass


class SecretPassage(SpaceCollection):
    """
    Secret Passage in the game
    """
    pass


class Card(models.Model):
    """
    A game Card.  Can either be a Room, Character, or Weapon
    """
    card_id = models.AutoField(primary_key=True) #had to override, due to multiple inheritence conflicts later
    name = models.CharField(max_length=30)

    def compare(self, otherCard):
        """
        Compares two Card objects
        :param otherCard: object of class Card
        :return: true if objects are equal, false otherwise
        """
        return(self.name == otherCard.name)

    def __str__(self):
        return(self.name)


class Room(SpaceCollection, Card):
    """
    Represents each room.
	"""
    pass


class Character(Card):
    """
    Represents each character in the game clue (the actual character, like Mr. Green)
	"""
    defaultSpace = models.ForeignKey(Space)
    characterColor = models.CharField(max_length=30)


class Weapon(Card):
    """
    Represents each weapon
	"""
    pass


class WhoWhatWhere(models.Model):
    """
    Class containing references to a Room, Weapon and Character.  A single instance of WhoWhereWhat is created at the
	start of the game as the confidential case file.  An instance of WhoWhereWhat is created every time an accusation or
	suggestion is made.
	"""
    character = models.ForeignKey(Character)
    weapon = models.ForeignKey(Weapon)
    room = models.ForeignKey(Room)

    def compare(self, otherWhoWhatWhere):
        """
        :param otherWhoWhatWhere: object of class WhoWhatWhere
        :return: true if room, character and weapon are all equal
        """
        roomEqual = self.room.compare(otherWhoWhatWhere.room)
        charEqual = self.character.compare(otherWhoWhatWhere.character)
        weaponEqual = self.weapon.compare(otherWhoWhatWhere.weapon)
        return(roomEqual and charEqual and weaponEqual)

    def __str__(self):
        return("character: {}, room: {}, weapon: {}".format(
            self.character.__str__(), self.room.__str__(), self.weapon.__str__()
        ))


class Turn(models.Model):
    """
    References the player, and contains a list of sequential actions performed by the player during one turn
    """
    player = models.ForeignKey(Player)
    game = models.ForeignKey('Game') #Game class not defined yet, referencing by string

    def __validate_action(self, action):
        if action.__class__ == Accusation:
            if Accusation.objects.filter(turn = self).count() > 1:
                logger.error("accusation already made")
                return False
            return True
        elif action.__class__ == Suggestion:
            if Suggestion.objects.filter(turn = self).count() > 1:
                logger.error("suggestion already made")
                return False
            elif Accusation.objects.filter(turn = self).count() > 0:
                logger.error("accusation already made")
                return False
            return True
        elif action.__class__ == Move:
            if Action.objects.filter(turn = self).count() > 1:
                logger.error("move must be first action")
                return False
            return True
        return False

    def getAvailableActions(self):
        """
        :return: Set of Action subclass class objects that can be taken at this point
        """
        #TODO: Implement this method
        return(None)

    def takeAction(self, action):
        """
        Performs an action
        :param action: Subclass of Action, which will have its performAction function called
        :return:
        """
        if not self.__validate_action(action):
            return ("Unable to perform action")
        if action.validate():
            action.performAction()
            return(None)
        else:
            return("Unable to perform action")

    def endTurn(self):
        """
        Ends this turn
        """
        currentPlayer = self.game.currentTurn.player
        players = Player.objects.filter(currentGame = self.game)
        for i, player in enumerate(players):
            if player.compare(currentPlayer):
                next_player = players[(i+1) % len(players)]
                break
        #creates a turn for next player
        turn = Turn(player=next_player, game=self.game)
        turn.save()
        self.game.currentTurn = turn
        self.game.save()


class Action(models.Model):
    """
    Any player action a player can take during a turn
    """
    turn = models.ForeignKey(Turn, blank=True)
    description = models.CharField(max_length=255, blank=True)

    def validate(self):
        """
        :return: boolean Can the action be validly taken
        """
        raise NotImplementedError("Subclasses of Action need to implement abstract method validate")

    def performAction(self):
        """
        Performs the action
        """
        raise NotImplementedError("Subclasses of Action need to implement abstract method performAction")


class Suggestion(Action):
    """
    A suggestion action taken by the player
    """
    whoWhatWhere = models.ForeignKey(WhoWhatWhere)

    @classmethod
    def createSuggestion(cls, turn, suspect, room, weapon):
        s = Suggestion()
        s.turn = turn
        www = WhoWhatWhere(character = suspect, room = room, weapon = weapon)
        www.save()
        s.whoWhatWhere = www
        s.save()
        return(s)

    def validate(self):
        #make sure user is in room
        if self.whoWhatWhere.room.id != self.turn.player.currentSpace.spaceCollector.id:
            return False
        return True

    def performAction(self):
        #move player being suggested
        accusedCharacter = self.whoWhatWhere.character
        accusedPlayer = Player.objects.get(currentGame = self.turn.game, character = accusedCharacter)
        accusedSpace = Space.objects.get(spaceCollector = self.whoWhatWhere.room)
        #move player
        accusedPlayer.currentSpace = accusedSpace
        accusedPlayer.save()


class Accusation(Action):
    """
    An accusation action taken by the player.  Either the player wins the game or they lose!
    """
    whoWhatWhere = models.ForeignKey(WhoWhatWhere)

    @classmethod
    def createAccusation(cls, turn, suspect, room, weapon):
        a = Accusation()
        a.turn = turn
        www = WhoWhatWhere(character=suspect, room=room, weapon=weapon)
        www.save()
        a.whoWhatWhere = www
        a.save()
        return (a)

    def validate(self):
        return True

    def performAction(self):
        if self.turn.game.isAccusationCorrect(self):
            self.turn.game.endGame(self.turn.player)
        else:
            self.turn.game.loseGame(self.turn.player)


class Move(Action):
    """
    Any move a player makes
    """
    fromSpace = models.ForeignKey(Space, related_name='fromSpace')
    toSpace = models.ForeignKey(Space, related_name='toSpace')

    def validate(self):
        #TODO: implement
        if (self.fromSpace.posX + 2 == self.toSpace.posX) or (self.fromSpace.posX - 2  == self.toSpace.posX) or (self.fromSpace.posY+ 2  == self.toSpace.posY) or (self.fromSpace.posY - 2  == self.toSpace.posY):
            return True
        else:
            return False

    def performAction(self):
        # TODO: implement
        pass


class CaseFile(WhoWhatWhere):
    """
    Class to be used for the secret CaseFile for a Game
    """
    @classmethod
    def createRandom(cls):
        """
        Static class method, to be used instead of constructor in most cases
        :return: CaseFile with random selections for room, character and weapon
        """
        randCaseFile = CaseFile()
        allChar = Character.objects.all()
        charCnt = allChar.count()
        allRoom = Room.objects.all()
        roomCnt = allRoom.count()
        allWeapon = Weapon.objects.all()
        weaponCnt = allWeapon.count()
        randCaseFile.character = allChar[random.randint(0, charCnt-1)]
        randCaseFile.room = allRoom[random.randint(0, roomCnt-1)]
        randCaseFile.weapon = allWeapon[random.randint(0, weaponCnt-1)]
        return(randCaseFile)


class Game(models.Model):
    """
    Parent game object
    """
    caseFile = models.ForeignKey(CaseFile)
    board = models.ForeignKey(Board)
    status = models.IntegerField(choices = STATUS_CHOICES, default = 0)
    startTime = models.DateTimeField(default = timezone.now(), blank = True)
    lastUpdateTime = models.DateTimeField(default=timezone.now(), blank=True)
    hostPlayer = models.ForeignKey(Player)
    name = models.CharField(max_length=60)
    currentSequence = models.IntegerField(default = 0)
    currentTurn = models.ForeignKey(Turn, related_name='currentTurn', blank=True, null=True)

    def initializeGame(self, playerHost):
        """
        Sets up a game with all the defaults
        :param playerHost: A player object representing the player that started the game
        :return:
        """
        self.hostPlayer = playerHost
        self.board = Board.objects.all()[0]
        self.status = NOT_STARTED
        randCaseFile = CaseFile.createRandom()
        randCaseFile.save()
        self.caseFile = randCaseFile
        self.registerGameUpdate()

    def unusedCharacters(self):
        """
        Gets a query set of character objects that have not been taken by a player yet
        :return:
        """
        usedCharacterIds = list()
        listOPlayers = Player.objects.filter(currentGame__id = self.id)
        for p in listOPlayers:
            usedCharacterIds.append(p.character.card_id)
        return Character.objects.exclude(card_id__in = usedCharacterIds)

    def startGame(self, user):
        """
        Starts a game
        :param user: user that will be the host
        """

        if self.status != 0:
            raise RuntimeError('Game already started')
        elif Player.objects.filter(currentGame__id=self.id).count() < 2:
            raise RuntimeError('Game must have at least 2 players')
        elif self.hostPlayer.user != user:
            raise RuntimeError('Game can only be started by host')
        else:
            self.status = STARTED

        turn = Turn(game = self, player = self.hostPlayer)
        turn.save()
        self.currentTurn = turn
        self.save()

        #get all of the games detective sheets
        detectiveSheetsQS = DetectiveSheet.objects.filter(game = self)
        #flatten/ not sure why I have to do this, but otherwise the indexing later doesn't work
        detectiveSheets = list()
        for ds in detectiveSheetsQS:
            detectiveSheets.append(ds)

        #get all cards that ARE NOT in the casefile
        cards = Card.objects.exclude(
            card_id = self.caseFile.character.card_id).exclude(
            card_id = self.caseFile.room.card_id).exclude(
            card_id = self.caseFile.weapon.card_id)

        #add these cards to a list, then shuffle
        cardList = list()
        for c in cards:
            cardList.append(c)

        random.shuffle(cardList)

        #deal the cards into each detective sheet
        for i in range(0, len(cardList)):
            dsIndex = i % len(detectiveSheets)
            detectiveSheets[dsIndex].makeNote(cardList[i], True, True)

        #create all the nonUser players for remaining characters
        #must happen after detectiveSheet logic because these players don't get detectiveSheets
        for c in self.unusedCharacters():
            nonUserPlayer = Player(character=c, currentSpace=c.defaultSpace, currentGame = self, nonUserPlayer = True)
            nonUserPlayer.save()

        #adds current turn to game
        player = Player.objects.get(user=user, currentGame=self)
        self.currentTurn = Turn.objects.get(player=player, game=self)

        self.save()
        self.registerGameUpdate()

    def isUserInGame(self, user):
        """
        Checks whether a user is in the game or not
        :param user:
        :return: True if user can join game
        """
        try:
            player = Player.objects.get(currentGame__id=self.id, user__id=user.id)
        except:
            return False
        return True

    def isCharacterInGame(self, character):
        """
        Checks whether the character is being used in the game
        :param character:
        :return:
        """
        return Player.objects.filter(currentGame__id = self.id, character__card_id = character.card_id).count() > 0

    def addPlayer(self, player):
        """
        Adds a player to the game
        :param player: Player to be added
        """
        if self.isUserInGame(player.user):
            raise RuntimeError("User is already a player in this game")
        elif self.isCharacterInGame(player.character):
            raise RuntimeError("Character is already in use")
        player.currentGame = self
        player.save()
        #give player a detective sheet
        ds = DetectiveSheet(game = self, player = player)
        ds.save()
        ds.addDefaultSheets()
        self.registerGameUpdate()

    def registerGameUpdate(self):
        """
        Updates the last update time to now, and increments the current game sequence
        """
        self.lastUpdateTime = timezone.now()
        self.currentSequence = self.currentSequence + 1
        self.save()

    def gameStateJSON(self, player):
        """

        :param player: Player we are rendering JSON for
        :return: a JSON representation of the current game state
        """
        #start gamestate dictionary, start adding fields
        gamestate = {}
        gamestate['game_sequence'] = self.currentSequence
        gamestate['isHostPlayer'] = self.hostPlayer == player
        gamestate['hostplayer'] = {'player_id':self.hostPlayer.id, 'username': self.hostPlayer.user.username}
        gamestate['status'] = self.status

        #develop a dictionary array of player status
        playerstates = []
        players = Player.objects.filter(currentGame = self)
        for p in players:
            c = p.character
            s = p.currentSpace
            pData={}
            if p.nonUserPlayer:
                pData = {
                    'player_id': p.id,
                    'username': 'not a user',
                    'character': {'character_id': c.card_id, 'character_name': c.name,
                                  'character_color': c.characterColor},
                    'currentSpace': {'space_id': s.id, 'posX': s.posX, 'posY': s.posY}
                }
            else:
                pData = {
                    'player_id':p.id,
                    'username':p.user.username,
                    'character':{'character_id':c.card_id, 'character_name':c.name, 'character_color':c.characterColor},
                    'currentSpace':{'space_id':s.id, 'posX':s.posX, 'posY':s.posY}
                }

            playerstates.append(pData)

        gamestate['playerstates'] = playerstates

        return gamestate

    def isAccusationCorrect(self, accusation):
        return self.caseFile.compare(accusation.whoWhatWhere)

    def endGame(self, winningPlayer):
        """
        Ends the game
        :param winningPlayer: Player who won
        """
        winningPlayer.gameResult = WON
        winningPlayer.save()

        for p in Player.objects.filter(currentGame = self).exclude(id = winningPlayer.id):
            p.gameResult = LOST
            p.save()

        self.status = 2
        self.save()

        self.registerGameUpdate()

    def loseGame(self, losingPlayer):
        """
        Ends the game for a losing player
        :param losingPlayer: Player who lost (bad accusation
        """
        losingPlayer.gameResult = LOST
        losingPlayer.save()
        self.registerGameUpdate()

    def __str__(self):
        return ("id: {}, name: {}".format(
            self.id, self.name
        ))


class DetectiveSheet(models.Model):
    """
    Detective Sheet a player fills out.  As card are discovered, a player checks off different cards as no longer
    possible
    """
    game = models.ForeignKey(Game)
    player = models.ForeignKey(Player)

    def __getCheckedCardIds(self):
        checkedSI = SheetItem.objects.filter(detectiveSheet = self, checked = True)
        checkedIds = list()
        for si in checkedSI:
            checkedIds.append(si.card.card_id)

        return checkedIds

    def addDefaultSheets(self):
        for c in Card.objects.all():
            si = SheetItem(detectiveSheet=self, card=c, checked=False, initiallyDealt=False)
            si.save()

    def getCharactersLeft(self):
        """
        :return: Set of Character objects that a player has not yet checked off
        """
        return (Character.objects.exclude(card_id__in=self.__getCheckedCardIds()))

    def getCharacterSheetItems(self):
        """
        :return: QuerySet of all sheet items relating to a character
        """
        charIds = Character.objects.all().values_list('card_id', flat=True)
        return SheetItem.objects.filter(detectiveSheet = self,  card__card_id__in=charIds).order_by("card__name")

    def getRoomsLeft(self):
        """
        :return: Set of Room object that a player has not yet checked off
        """
        return (Room.objects.exclude(card_id__in=self.__getCheckedCardIds()))

    def getRoomSheetItems(self):
        """
        :return: QuerySet of all sheet items relating to a room
        """
        roomIds = Room.objects.all().values_list('card_id', flat=True)
        return SheetItem.objects.filter(detectiveSheet = self,  card__card_id__in=roomIds).order_by("card__name")

    def getWeaponsLeft(self):
        """
        :return: Set of Weapon objects that a player has not yet checked off
        """
        return (Weapon.objects.exclude(card_id__in = self.__getCheckedCardIds()))

    def getWeaponSheetItems(self):
        """
        :return: QuerySet of all sheet items relating to a weapon
        """
        weaponIds = Weapon.objects.all().values_list('card_id', flat=True)
        return SheetItem.objects.filter(detectiveSheet = self,  card__card_id__in=weaponIds ).order_by("card__name")

    def makeNote(self, card, checked, initiallyDealt = False, manuallyChecked = False):
        """
        Notes whether a player has checked off a particular card or not
        :param card: Card that is being checked off
        :param checked: boolean whether to check or uncheck
        """
        si = SheetItem.objects.get(detectiveSheet = self, card = card)
        si.checked = checked
        si.initiallyDealt = initiallyDealt
        si.manuallyChecked = manuallyChecked
        si.save()


class SheetItem(models.Model):
    """
    A sheet item is an item on a DectiveSheet, and represents whether a user has checked off a specific card yet
    """
    detectiveSheet = models.ForeignKey(DetectiveSheet)
    card = models.ForeignKey(Card)
    checked = models.BooleanField(default = False)
    initiallyDealt = models.BooleanField(default = False)
    manuallyChecked = models.BooleanField(default = False)

    def __str__(self):
        return ("user: {}, game: [{}], card: {}, checked: {}".format(
            self.detectiveSheet.player.user.__str__(), self.detectiveSheet.game.__str__(), self.card.__str__(), self.checked.__str__()
        ))
