#!/usr/bin/env python3

import argparse
import os
import random
import tempfile

import chess
import chess.pgn
import chess.svg

import genanki

PIXEL_SIZE = 400
WORK_DIR = os.path.join(tempfile.gettempdir(), str(os.getpid()))

IMAGE_MODEL = genanki.Model(
	1536607853, #unique ID
	"Chess PGN Image Model",
	fields=[
		{"name" : "Current"},
		{"name" : "Next"},
	],
	templates=[
		{
			"name" : "Image Card",
			"qfmt" : "{{Current}}",
			"afmt" : "{{Next}}"
		}
	])

NOTATION_MODEL = genanki.Model(
	1089711253,
	"Chess PGN Notation Model",
	fields=[
		{"name" : "Current"},
		{"name" : "Next"},
	],
	templates=[
		{
			"name" : "Notation Card",
			"qfmt" : "{{Current}}",
			"afmt" : "{{FrontSide}}<hr id='answer'>{{Next}}"
		}
	],
	css=".card {font-family: arial;font-size: 18px;line-height: 120%;text-align: center;}")

def gen_id():
	return random.randrange(1<<30, 1 << 31)

def iterate(game, mainline=False):
	"""
	Iterate over the child nodes of a game.
	
	Parameters
	----------
	game : chess.pgn.Game
		A game to iterate over.
	mainline : bool, default=False
		If True, only iterate over the mainline, else visit all nodes.
		
	yields
	------
	chess.pgn.GameNode
		Some decendent of the root node: game.
	"""
	if mainline:
		for child_node in game.mainline():
			yield child_node	
		return
	for child_node in game.variations:
		if not child_node.starts_variation(): # this condition blocks cards with multiple answers
			yield child_node
		for grandchild_node in iterate(child_node):
			yield grandchild_node

def game_node_hash(game_node):
	"""
	Creates a unique hash of a game node.
	Hashes are created with respect to the current state of the board and the
	move that put it in that state.
	
	Parameters
	----------
	game_node : chess.pgn.GameNode
		Some node to hash.
		
	Returns
	-------
	str
		A hash value.
	"""
	board = game_node.board()
	if game_node is game_node.game(): #is root node, ie no (recorded) move lead to this position
		h = board.fen()
	else:
		h = '_'.join([board.fen(), game_node.san()])
	h = h.replace("/", "_")
	h = h.replace(" ", "_")
	return h

def full_path(file_name):
	"""
	Returns the file name as if it were listed in the work directory.
	
	Parameters
	----------
	file_name : str
		Some file name.
		
	Returns
	-------
	str
	"""
	return os.path.join(WORK_DIR, file_name)

def write_svg(game_node, flip, arrows, coordinates):
	"""
	Writes an SVG file to disk based on a game node.
	The image created is of the current state of the chess board with the most
	recent move highlighted (if applicable).
	
	Parameters
	----------
	game_node : chess.pgn.GameNode
		A node to create an image for.
	
	flip : bool
		If true, flip the generated image to show from black's perspective.
		
	arrows : bool
		If true, draw arrows as described in the PGN.
		
	Returns
	-------
	str : file_name
		The file name of the created image.
	Note: The created file names are hashable, and no duplicate images are
	      created during run-time.
	"""
	hash_val = game_node_hash(game_node)
	file_name = f"{('+','-')[flip]}{hash_val}.svg"
	if file_name in write_svg.file_names:
		return file_name
	image = chess.svg.board(board=game_node.board(), lastmove=game_node.move, size=PIXEL_SIZE, flipped=flip, arrows = game_node.arrows() if arrows else [], coordinates=coordinates)
	with open(full_path(file_name), "w") as f:
		f.write(image)
	write_svg.file_names.append(file_name)
	return file_name
write_svg.file_names=[] #static var used to avoid re-creating any images

def image_data(game, mainline, flip, white, black, arrows, coordinates):
	"""
	Generate question/answer/question comment/answer comment quadruplets for a game using images.
	
	Parameters
	----------
	game : chess.pgn.Game
		A game to generate questions and answers from.
	mainline : bool
		If true, only generate questions and answers for the mainline, else
		generate values for all nodes.
	flip : bool
		if true, flip generated images to view from black's perspective.
	white : bool
		If true, only create images where white is to move.
	black : bool
		If true, only create images where black is to move. If both white and black are true, white only will be drawn.
	arrows : bool
		If true, draw images as described in the PGN.
		
	Yields
	------
	(question, answer, qcomment, acomment) : (str, str, str, str)
		question, answer : file names for images describing the relevant question and answer.
		qcomment, acomment : comments for the question and answer
	"""
	if white:
		for child_node in iterate(game, mainline):
			if child_node.parent.turn() == chess.WHITE:
				yield draw(child_node, flip, arrows, coordinates)
	elif black:
		for child_node in iterate(game, mainline):
			if child_node.parent.turn() == chess.BLACK:
				yield draw(child_node, flip, arrows, coordinates)
	else:
		for child_node in iterate(game, mainline):
			yield draw(child_node, flip, arrows, coordinates)

def draw(node, flip, arrows, coordinates):
	"""
	Draw question/answer images and organize them into quadruplets alongside their comments.
	
	Parameters
	----------
	node : chess.pgn.GameNode
		The node to create a quadruplet for.
	
	flip : bool
		If true, flip the generated image to show from black's perspective.
		
	arrows : bool
		If true, draw arrows as described in the PGN.

	Returns
	-------
	(question, answer, qcomment, acomment) : (str, str, str, str)
		question, answer : file names for images describing the relevant question and answer.
		qcomment, acomment : comments for the question and answer
	"""		
	question = write_svg(node.parent, flip, arrows, coordinates)
	answer   = write_svg(node, flip, arrows, coordinates)
	qcomment = node.parent.comment.split('[')[0] 
	acomment = node.comment.split('[')[0]
	return (question, answer, qcomment, acomment)


def notation_data(game):
	"""
	Generate question/answer pairs for a game using SAN notation.
	Note: Only mainline nodes will have values generated for them.
	
	Parameters
	----------
	game : chess.pgn.Game
		A game to generate questions and answers from.
		
	Yields
	------
	(question, answer) : (str, str)
		SAN notation for the relevant move in a question/answer format.
	"""
	for child_node in iterate(game):
		turn = (child_node.parent.ply() // 2)+1
		move = child_node.san()
		if child_node.parent.turn() == chess.WHITE:
			question = f"{turn}. ?"
			answer   = f"{turn}.{move}"
		else:
			question = f"{turn}... ?"
			answer   = f"{turn}... {move}"
		yield (question, answer)

def generate(game, out, title, blindfold=False, mainline=True, flip=False, white=False, black=False, arrows=False, coordinates=True):
	"""
	Generate an Anki deck from a game.
	
	Parameters
	----------
	game : chess.pgn.Game
		A game to generate cards for.
	out : str
		The file name of the Anki package(.apkg) to generate.
	title : str
		The title to give the generated deck as seen in the Anki GUI.
	blindfold : bool, Default=False
		If True, generate cards with text notation only, no images.
		Implies mainline=True.
	mainline : bool, Default=True
		if True, only generate cards for the mainline moves.
	flip : bool, Default=False
		if True, flip the generated images to view from black's perspective
		Implies blindfold=False.
	"""
	media = []
	deck = genanki.Deck(gen_id(), title)
	if blindfold:
		for question, answer in notation_data(game):
			note = genanki.Note(model=NOTATION_MODEL, fields=[question, answer])
			deck.add_note(note)
		package = genanki.Package(deck)
	else:
		for question, answer, qcomment, acomment in image_data(game, mainline, flip, white, black, arrows, coordinates):
			media.append(os.path.join(WORK_DIR, question))
			media.append(os.path.join(WORK_DIR, answer))
			question = f"<img style=\"display: block; margin-left: auto; margin-right: auto;\" src=\"{question}\"><p style=\"font-size: 28px; text-align: center;\">{qcomment}</p>"
			answer   = f"<img style=\"display: block; margin-left: auto; margin-right: auto;\" src=\"{answer}\"><p style=\"font-size: 28px; text-align: center;\">{acomment}</p>"
			note = genanki.Note(model=IMAGE_MODEL, fields=[question, answer])
			deck.add_note(note)
		media = set(media)
		package = genanki.Package(deck, media)
	package.write_to_file(out)
	#cleanup
	for filename in media:
		os.remove(filename)

def get_game(file_name, n):
	game = None
	with open(file_name, "r") as f:
		for _ in range(n):
			game = chess.pgn.read_game(f)
	if not game:
		raise RuntimeError
	return game

def main(args):
	try:
		game = get_game(args.pgn, args.game)
	except RuntimeError:
		raise SystemExit(f"could not load game {args.game} from pgn file {args.pgn}")
	except FileNotFoundError:
		raise SystemExit(f"could not find pgn file {args.pgn}")
	if not args.blindfold: #temp dir to make images
		os.makedirs(WORK_DIR, exist_ok=False)
	generate(game, args.out, args.title, args.blindfold, args.mainline, args.flip, args.white, args.black, args.arrows, args.coordinates)
	if not args.blindfold:
		os.rmdir(WORK_DIR)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Generate Anki packages from chess PGN files")
	parser.add_argument("pgn", type=str, metavar="PGN_FILE",          help="A PGN file to generate an Anki package from (mainline only)")
	parser.add_argument("out", type=str, metavar="OUT_FILE",          help="The file name of the Anki package to generate (typically ending in .apkg)")
	parser.add_argument("title", type=str, metavar="TITLE",           help="The title to give the generated deck as seen in the Anki GUI")
	parser.add_argument("--mainline", action="store_true",            help="Only generate cards for the mainline moves")
	parser.add_argument("--blindfold", action="store_true",           help="Generate cards with text notation only, no images (Implies --mainline)")
	parser.add_argument("--flip", action="store_true", help="Flip the generated images to view from black's perspective (Does nothing if --blindfold)")
	parser.add_argument("--game", type=int, default=1, metavar="NUM", help="Select the Nth game from the PGN file (Default is 1)")
	parser.add_argument("--white", action="store_true",           help="Generate cards only when it is white to play")
	parser.add_argument("--black", action="store_true",           help="Generate cards only when it is black to play")
	parser.add_argument("--arrows", action="store_true",			help="Draw arrows and circles on board")
	parser.add_argument("--coordinates", action="store_false", help="Disable coordinates on images")
	args = parser.parse_args()

	main(args)
