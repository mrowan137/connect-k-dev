import sys, time
from collections import defaultdict, deque

from flask import Flask, session, request, make_response, render_template, render_template_string, redirect, url_for, escape
from flask_caching import Cache
from wtforms import Form, IntegerField, SelectField, validators
from uuid import uuid4


class Input(Form):
    k = IntegerField(label="Select a value for k: ",
                     default=3,
                     validators=[validators.InputRequired(),
                                 validators.NumberRange(min=1,
                                                        max=2147483647,
                                                        message="Input a number in the range [0, 2147483647]!")])

    player_color = SelectField(label="Choose your color: ",
                               default="Red",
                               choices=["Red", "Blue"],
                               render_kw={'style': 'width: 100%'},
                               validators=[validators.InputRequired(),
                                           validators.AnyOf(["Red", "Blue"],
                                                            message="Select Red or Blue.",
                                                            values_formatter=None)])
    
    first_player = SelectField(label="Who goes first?",
                             default="Red",
                             choices=["Red", "Blue"],
                             render_kw={'style': 'width: 100%'},
                             validators=[validators.InputRequired(),
                                         validators.AnyOf(["Red", "Blue"],
                                                          message="Select Red or Blue.",
                                                          values_formatter=None)])

    opponent = SelectField(label="Choose opponent: ",
                           default="Human",
                           choices=["Human", "Computer"],
                           render_kw={'style': 'width: 100%'},
                           validators=[validators.InputRequired(),
                                       validators.AnyOf(["Human", "Computer"],
                                                        message="Select Human or Computer.",
                                                        values_formatter=None)])


class ConnectK(object):
    def __init__(self, k=None, player_color=None, current_player=None, opponent=None,
                 M=10, N=17, board_=defaultdict(deque)):
        # inputs
        self.k_ = k
        self.player_color_ = player_color
        self.current_player_ = current_player
        self.opponent_ = opponent

        # initial ranges to display the board
        self.M_ = M
        self.N_ = N
        
        # board
        self.board_ = board_
        self.SetBoardDisplay_(self.M_, self.N_, 0)

        # control
        self.moves_list_ = deque()
        self.game_over_ = False

        
    def SetBoardDisplay_(self, M, N, center):
        # set the display centered around a move 'center'
        
        # set row and column coordinates
        self.board_display_ = [[""  for j in range(self.N_)] for i in range(self.M_)]
        for j in range(1, self.N_): self.board_display_[self.M_ - 1][j] = center - self.N_//2 + j
        for i in range(self.M_ - 2, -1, -1): self.board_display_[(self.M_ - 2) - i][0] = i

        # fill in the rest of the board
        for j in range(1, self.N_):
            col = center - self.N_//2 + j 
            if col in self.board_:
                for i in range(len(self.board_[col])):
                    self.board_display_[self.M_ - 2 - i][j] = 'R' if self.board_[col][i] == 0 else 'B'

                    
    def ResetBoard_(self):
        self.board_.clear()
        self.current_player_ = None
        self.M_, self.N_ = 10, 17
        self.board_display_ = [[""  for j in range(self.N_)] for i in range(self.M_)]

                
    def CheckForGameOver_(self, player, forecast=False):
        winner  = None
        winning_move_i = None
        for j in self.board_:
            # vertical check
            i, count = 0, 0
            while ( i < len(self.board_[j])
                    and count < self.k_
                    and self.board_[j][i] == player):
                i += 1
                count += 1
                
            if count == self.k_:
                winner = "R" if player == 0 else "B"
                if not forecast:
                    self.game_over_ = True
                    self.winner_ = winner
                    
                winning_move_i = 0
                return winner, winning_move_i
            
            # horizontal check
            i = 0
            while ( i < len(self.board_[j]) ):
                if self.board_[j][i] != player:
                    i += 1
                    continue
                
                count = 1
                l = j - 1
                while ( l in self.board_
                        and i < len(self.board_[l])
                        and self.board_[l][i] == player):
                    count += 1
                    l -= 1

                r = j + 1
                while ( r in self.board_
                        and i < len(self.board_[r])
                        and self.board_[r][i] == player):
                    count += 1
                    r += 1

                if count >= self.k_:
                    winner = "R" if player == 0 else "B"
                    if not forecast:
                        self.game_over_ = True
                        self.winner_ = winner

                    winning_move_i = i
                    return winner, winning_move_i
                
                i += 1

        return winner, winning_move_i


    def GameOver_(self):
        return self.game_over_
    

    def ToggleCurrentPlayer_(self):
        self.current_player_ = (self.current_player_ + 1)%2

        
    def PlayMove_(self, move):
        # play the move
        self.moves_list_.appendleft(move)
        self.board_[move].appendleft(self.current_player_)
        
        # update whose turn it is
        self.ToggleCurrentPlayer_()

        
    def UnplayMove_(self):
        if len(self.moves_list_) == 0: return
        
        # unplay the move
        self.ToggleCurrentPlayer_()
        move = self.moves_list_.popleft()
        self.board_[move].popleft()
        if not self.board_[move]: del self.board_[move]
        
        
    def UpdateDisplay_(self):
        if not self.moves_list_: return
        # update the display
        self.M_ = max(max([len(col) + 1 for col in self.board_.values()]), self.M_)
        self.SetBoardDisplay_(self.M_, self.N_, self.moves_list_[0])

        
    def ComputeMove_(self):
        if not self.moves_list_: return 0
        # consider a move within the range of moves so far
        l, r = min(self.board_) - 1, max(self.board_) + 1
        me = self.current_player_
        opponent = not me
        
        # if it's a winning move for computer, we'll take it; a draw is OK
        for j in range(l, r+1):
            self.PlayMove_(j)
            computer_winner, _ = self.CheckForGameOver_(self.opponent_color_, forecast=True)
            self.UnplayMove_()
            if computer_winner:
                return j

        # if it's a winning move for the computer's opponent (the human), we'll block it
        for j in range(l, r+1):
            self.ToggleCurrentPlayer_()
            self.PlayMove_(j)
            player_winner, player_winning_move_i = self.CheckForGameOver_(self.player_color_, forecast=True)
            self.UnplayMove_()
            self.ToggleCurrentPlayer_()
            if player_winner:
                if j in self.board_ and self.board_[j] and self.board_[j][0] == self.player_color_ and player_winning_move_i == 0:
                    # this could be a vertical or horizontal victory, distinguish by the returned i location
                    blocking_move = j
                else:
                    if ( j - 1 in self.board_
                         and player_winning_move_i < len(self.board_[j - 1])
                         and self.board_[j - 1][player_winning_move_i] == self.player_color_):
                        blocking_move = j - 1
                    else:
                        blocking_move = j + 1
                
                return blocking_move

        # otherwise, take a move that tries to maximize computer's contiguous blocks
        # and minimize the human's contiguous blocks
        best_move = 0
        score = float('-inf')
        for j in range(l, r+1):
            self.PlayMove_(j)
            my_contiguous_blocks = self.CountAdjacentBlocks_(j, me)
            opponent_contiguous_blocks = self.CountAdjacentBlocks_(j, opponent)
            best_score_so_far = score
            
            # this is just a weighting chosen on intuition, it could be experimented with
            # for computer to have more aggressive or defensive strategy;
            # also add a small bonus for displacing an opponent piece
            score = max(  0.0*my_contiguous_blocks
                        - 1.0*opponent_contiguous_blocks
                        + 1e-5*(len(self.board_[j]) >= 2 and self.board_[j][1] == opponent),
                          best_score_so_far)

            # make sure we don't take a move that cause the other player to win
            player_winner, _ = self.CheckForGameOver_(self.player_color_, forecast=True)
            best_move = j if score > best_score_so_far and not player_winner else best_move
            self.UnplayMove_()

        return best_move

    
    def CountAdjacentBlocks_(self, move, player):
        # vertical count
        i, count = 0, 0
        while ( self.board_[move]
                and i < len(self.board_[move]) - 1
                and self.board_[move][i] == player
                and self.board_[move][i] == self.board_[move][i+1]):
            count += 1
            i += 1
        
        # horizontal check
        i = 0
        while ( self.board_[move] and i < len(self.board_[move]) ):
            if self.board_[move][i] != player:
                i += 1
                continue
        
            l = move - 1
            r = move + 1
            
            if ( r in self.board_ and i < len(self.board_[r]) and self.board_[r][i] == player): count += 1
            if ( l in self.board_ and i < len(self.board_[l]) and self.board_[l][i] == player): count += 1
        
            i += 1
        
        return count
        
        
BOARD_DISPLAY_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <title>CONNECT-K</title>
    <link href="/static/style.css" rel="stylesheet" type="text/css">
    <!-- <link rel="stylesheet" type="text/css" href="/static/style.css"> -->
     {{"<!--"|safe if not ck.computer_is_thinking}} <script>
       setTimeout(function(){window.location.href = "{{ url_for("play",
                                                               k=ck.k_,
                                                               player_color=ck.player_color_,
                                                               first_player=ck.first_player_,
                                                               opponent=ck.opponent_
                                                   ) }}";}, 800);
     </script>
     {{"-->"|safe if not ck.computer_is_thinking}}
  </head>
  <body style="text-align:center">
    <h1 style="text-align:center; font-family: 'Press Start 2P';">CONNECT-K={{ck.k_}}</h1>
    <h2 style="font-family: 'Press Start 2P'">{{msg|safe}}</h2>
    <form action="" method="POST">
      <table style="margin-left:auto; margin-right: auto;">
        {% for i in range(ck.M_) %}        
          <tr>
            {% for j in range(ck.N_) %}
              <td>
                <button type="submit" 
                        class="button {{' big_on_hover' if (i == ck.M_ - 2) and (j != 0) and ck.GameOver_() == False and ck.computer_is_thinking == False else ""}}
                                      {{' glowing_border' if (j ==  ck.N_//2) and (i == ck.M_ - 2) and ck.moves_list_}}" 
                        name="move" value="{{(0 if not ck.moves_list_ else ck.moves_list_[0]) - ck.N_//2 + j}}" 
                        style="height:50px; 
                               width:50px;
                               border-radius: 4px;
                               background-color:{{"Crimson" if ck.board_display_[i][j] == "R" else ("DarkBlue" if ck.board_display_[i][j] == "B" else "transparent")}};
                               color:{{"white" if ck.board_display_[i][j] in ["R", "B"] else "black"}};
                               "
                               {{"disabled" if (i != ck.M_ - 2) or (j == 0) or ck.GameOver_() == True or ck.computer_is_thinking == True}}>
                  {{ck.board_display_[i][j]}}
                </button>
              </td>
            {% endfor %}
          </tr>
        {% endfor %}
      </table>
      <button type="submit" name="reset">Start a new game</button>
    </form>
  </body>
</html>
"""


app = Flask(__name__)
app.config['SECRET_KEY'] = "9dda556f72ee403bab999bbc5a6e6808"
c = Cache(app, config={"CACHE_TYPE": "filesystem",
                       "CACHE_DIR": "/tmp",
                       'CACHE_THRESHOLD': 0,
                       "CACHE_DEFAULT_TIMEOUT": 0,
                       "SECRET_KEY": "9dda556f72ee403bab999bbc5a6e6808"})

def GenerateId():
    return uuid4().__str__()


def LoadGame():
    if "game_id" in session:
        ck = c.get(session["game_id"])
    else:
        ck = ConnectK()
        
    return ck


def SaveGame(game):
    done = False
    while not done:
        if "game_id" in session:
            c.set(session["game_id"], game)
            if c.get(session["game_id"]): done = True
        else:
            unique_id = GenerateId()
            session["game_id"] = unique_id
            c.set(unique_id, game)
            if c.get(unique_id): done = True
        

@app.route("/", methods=["GET", "POST"])
def root():
    if "game_id" in session: del session["game_id"]
    
    form = Input(request.form)
    if request.method == "POST" and form.validate():
        response = make_response( redirect(url_for("play",
                                                   k=str(escape(form.k.data)),
                                                   player_color=str(escape(form.player_color.data)),
                                                   first_player=str(escape(form.first_player.data)),
                                                   opponent=str(escape(form.opponent.data))
                                                   )))
    else:
        response = make_response( render_template("input.html", form=form, result=None) )

    # warmup the cache
    ck = None
    for i in range(4):
        ck = LoadGame()
        SaveGame(ck)
        
    if not ck: return redirect(url_for("root"))
    
    return response
    
    
@app.route("/play/<k>/<player_color>/<first_player>/<opponent>/", methods=["GET", "POST"])
def play(k=None, player_color=None, first_player=None, opponent=None):
    ck = LoadGame()
    if not ck: return redirect(url_for("root"))
    if (    ck.k_              == None
        and ck.player_color_   == None
        and ck.current_player_ == None
        and ck.opponent_       == None ):
        ck.k_ = int(k)
        ck.player_color_ = 0 if player_color == "Red" else 1
        ck.opponent_color_ = not ck.player_color_
        ck.current_player_ = ck.first_player_ = 0 if first_player == "Red" else 1
        ck.opponent_ = opponent
        ck.computer_is_thinking = True if opponent == "Computer" and ck.player_color_ != ck.current_player_ else False

    # computer opponent's turn
    if ck.computer_is_thinking:
        msg = "<p><span style=\"color: {};\">Computer</span> is thinking...</p>".format("Crimson" if ck.current_player_ == 0 else "DarkBlue")
        response = make_response(render_template_string(BOARD_DISPLAY_TEMPLATE, ck=ck, msg=msg))
        ck.computer_is_thinking = False
        mv = ck.ComputeMove_()
        ck.PlayMove_(mv)
        SaveGame(ck)
        return response

    if (ck.current_player_ != ck.player_color_ and ck.opponent_ == "Computer"):
        ck.UpdateDisplay_()
        SaveGame(ck)

    if "reset" in request.form:
        ck.ResetBoard_()
        SaveGame(ck)
        return redirect(url_for("root"))
    
    winner, opponent_winner = None, None
    if "move" in request.form:
        ck.PlayMove_(int(request.form["move"]))
        if ck.opponent_ == "Computer": ck.computer_is_thinking = True
        
    # check if the game is over for the player
    winner, _ = ck.CheckForGameOver_(ck.player_color_)
    
    # check if game is over for the opponent
    opponent_winner, _ = ck.CheckForGameOver_(ck.opponent_color_)
    
    ck.UpdateDisplay_()
        
    if winner or opponent_winner:
        if winner and opponent_winner:
            msg = "It's a draw!"
        else:
            winner = winner if winner else opponent_winner
            msg = "<p><span style=\"color: {};\"> Player {}</span> ({}) is the winner!</p>".format("Crimson" if winner == "R" else "DarkBlue", winner, ck.opponent_ if winner == opponent_winner else "Human")
        
        if ck.opponent_ == "Computer": ck.computer_is_thinking = False

    else:
        if (ck.current_player_ != ck.player_color_ and ck.opponent_ == "Computer"):
            msg = "<p><span style=\"color: {};\">Computer</span> is thinking...</p>".format("Crimson" if ck.current_player_ == 0 else "DarkBlue")
        else:
            msg = "<p>Player <span style=\"color: {};\">{}</span> it's your turn</p>".format( "Crimson" if ck.current_player_ == 0 else "DarkBlue", "R" if ck.current_player_ == 0 else "B")            

    response = make_response(render_template_string(BOARD_DISPLAY_TEMPLATE, ck=ck, msg=msg))

    SaveGame(ck)
    return response
    

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True, threaded=False)
