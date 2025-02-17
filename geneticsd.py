# A ton of imports.
from gfpgan.utils import GFPGANer
import cv2
import random
import os
import time
import torch
import numpy as np
import shutil
import PIL
from PIL import Image
from einops import rearrange, repeat
from torch import autocast
from diffusers import StableDiffusionPipeline
from deep_translator import GoogleTranslator
from langdetect import detect
from joblib import Parallel, delayed
import torch
from PIL import Image
from RealESRGAN import RealESRGAN
import pyttsx3
import pyfiglet
import pygame
from os import listdir
from os.path import isfile, join

# Let's parametrize a few things.
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
model_id = "CompVis/stable-diffusion-v1-4"
device = "mps" #torch.device("mps")

# Let us define colors.
white = (255, 255, 255)
green = (0, 255, 0)
darkgreen = (0, 128, 0)
red = (255, 0, 0)
blue = (0, 0, 128)
black = (0, 0, 0)

# A few environment variables and variables.
os.environ["skl"] = "tree"
os.environ["epsilon"] = "0.005"
os.environ["decay"] = "0."
os.environ["ngoptim"] = "DiscreteLenglerOnePlusOne"
os.environ["forcedlatent"] = ""
latent_forcing = ""
os.environ["good"] = "[]"
os.environ["bad"] = "[]"
num_iterations = 50
gs = 7.5
sentinel = str(random.randint(0,100000)) + "XX" +  str(random.randint(0,100000))
all_files = []
llambda = 15
sigma = 1.

# Creating the voice engine.
noise = pyttsx3.init()
noise.setProperty("rate", 240)
def speak(text):
     noise.say(text)
     noise.runAndWait()

# Let us define our latent var combinators (including the cross-over Voronoi).
def multi_combine(latent, indices, llambda):
    """outputs = multi_combine(latent, indices, llambda)

    Creates Voronoi combinations of images.

Inputs:
    indices  triplets corresponding to selected images.
             E.g. indices = [(0, .3, .7), (2, .5, .5), (0, .3, .3)]
             means that the user likes points at abscissa/ordinate (.3,.7) and (.3,.3)
             of the first image (image with index 0) and point in the middle of the
             image with index 2.
    latent   list of the latent variables associated to images.
             We need len(latent) > max([i[0] for i in dices])
    llambda  number of images to generate

Output:
    a vector of llambda latent variables.
"""
    outputs = []
    good_indices = [i[0] for i in indices]
    for a in range(llambda):
#        voronoi_in_images = False
#        if voronoi_in_images:  # This is not used for now.
#            image = np.array(numpy_images[0])
#            print(f"Voronoi in the image space! {a} / {llambda}")
#            for i in range(len(indices)):
#                coefficients[i] = np.exp(np.random.randn())
#            # Creating a forcedlatent.
#            for i in range(512):
#                x = i / 511.
#                for j in range(512):
#                    y = j / 511 
#                    mindistances = 10000000000.
#                    for u in range(len(indices)):
#                        distance = coefficients[u] * np.linalg.norm( np.array((x, y)) - np.array((indices[u][2], indices[u][1])) )
#                        if distance < mindistances:
#                            mindistances = distance
#                            uu = indices[u][0]
#                    image[i][j][:] = numpy_images[uu][i][j][:]
#            pil_image = Image.fromarray(image)
#            basic_new_fl = randomized_image_to_latent(voronoi_name)
#            basic_new_fl = np.sqrt(len(basic_new_fl) / np.sum(basic_new_fl**2)) * basic_new_fl
#            if len(good_indices) > 1:
#                print("Directly copying latent vars !!!")
#                outputs += [basic_new_fl]
#            else:
#                epsilon = 1.0 * (((a + .5 - len(good)) / (llambda - len(good) - 1)) ** 2)
#                forcedlatent = (1. - epsilon) * basic_new_fl.flatten() + epsilon * np.random.randn(4*64*64)
#                forcedlatent = np.sqrt(len(forcedlatent) / np.sum(forcedlatent**2)) * forcedlatent
#                outputs += [forcedlatent]
#        else:
        if True:
            ratio = np.random.randn()
            print(f"Voronoi in the latent space! {a} / {llambda}")
            forcedlatent = np.zeros((4, 64, 64))
            for i in range(64):
                x = i / 63.
                for j in range(64):
                    y = j / 63
                    mindistances = 500000.
                    mindistancesv = 500000. * np.ones(1 + np.max([i[0] for i in indices]))
                    for u in range(len(indices)):
                        distance = np.linalg.norm( np.array((x, y)) - np.array((indices[u][2], indices[u][1])) )
                        if distance < mindistancesv[indices[u][0]]:
                            mindistancesv[indices[u][0]] = distance
                        if distance < mindistances:
                            mindistances = distance
                            uu = indices[u][0]
                    for k in range(4):
                        assert k < len(forcedlatent), k
                        assert i < len(forcedlatent[k]), i
                        assert j < len(forcedlatent[k][i]), j
                        assert uu < len(latent)
                        assert k < len(latent[uu]), k
                        assert i < len(latent[uu][k]), i
                        assert j < len(latent[uu][k][i]), j
                        forcedlatent[k][i][j] = float(latent[uu][k][i][j] if (len(good_indices) < 2 or mindistances < ratio * np.min([mindistancesv[v] for v in range(len(mindistancesv)) if v != uu])) else np.random.randn())
            forcedlatent = forcedlatent.flatten()
            basic_new_fl = np.sqrt(len(forcedlatent) / np.sum(forcedlatent**2)) * forcedlatent
            if len(good_indices) > 1:
                print(f"Directly copying for {a} / {llambda}")
                outputs += [basic_new_fl]
            else:
                print("Perturbating the generation!")
                epsilon = sigma * (( (a + .5 - len(good)) / (llambda - len(good) - 1)))
                forcedlatent = (1. - epsilon) * basic_new_fl + epsilon * np.random.randn(4*64*64)
                coef =  np.sqrt(len(forcedlatent) / np.sum(forcedlatent**2))
                forcedlatent = coef * forcedlatent
                outputs += [forcedlatent]
    return outputs


# Initialization.
all_selected = []        # List of all selected images, over all the run.
all_selected_latent = [] # The corresponding latent variables.
final_selection = []     # Selection of files during the final iteration.
final_selection_latent = []     # Selection of files during the final iteration.
forcedlatents = []       # Latent variables that we want to see soon.
forcedgs = []            # forcedgs[i] is the guidance strength that we want to see for image number i.
assert llambda < 16, "lambda < 16 for convenience in pygame."
bad = []
five_best = []
latent = []
images = []
onlyfiles = []

# Creating the main pipeline.
assert False, "Please create a token at https://huggingface.co/login?next=%2Fsettings%2Ftokens and put it below. Then, remove this line."
pipe = StableDiffusionPipeline.from_pretrained(model_id, use_auth_token="XXXXX")
pipe = pipe.to(device)

 
# A ton of prompts, for fun.
prompt = "a photo of an astronaut riding a horse on mars"
prompt = "a photo of a red panda with a hat playing table tennis"
prompt = "a photorealistic portrait of " + random.choice(["Mary Cury", "Scarlett Johansson", "Marilyn Monroe", "Poison Ivy", "Black Widow", "Medusa", "Batman", "Albert Einstein", "Louis XIV", "Tarzan"]) + random.choice([" with glasses", " with a hat", " with a cigarette", "with a scarf"])
prompt = "a photorealistic portrait of " + random.choice(["Nelson Mandela", "Superman", "Superwoman", "Volodymyr Zelenskyy", "Tsai Ing-Wen", "Lzzy Hale", "Meg Myers"]) + random.choice([" with glasses", " with a hat", " with a cigarette", "with a scarf"])
prompt = random.choice(["A woman with three eyes", "Meg Myers", "The rock band Ankor", "Miley Cyrus", "The man named Rahan", "A murder", "Rambo playing table tennis"])
prompt = "Photo of a female Terminator."
prompt = random.choice([
     "Photo of Tarzan as a lawyer with a tie",
     "Photo of Scarlett Johansson as a sumo-tori",
     "Photo of the little mermaid as a young black girl",
     "Photo of Schwarzy with tentacles",
     "Photo of Meg Myers with an Egyptian dress",
     "Photo of Schwarzy as a ballet dancer",
    ])
name = random.choice(["Mark Zuckerbeg", "Zendaya", "Yann LeCun", "Scarlett Johansson", "Superman", "Meg Myers"])
prompt = f"Photo of {name} as a sumo-tori."

prompt = "Full length portrait of Mark Zuckerberg as a Sumo-Tori."
prompt = "Full length portrait of Scarlett Johansson as a Sumo-Tori."
prompt = "A close up photographic portrait of a young woman with uniformly colored hair."
prompt = "Zombies raising and worshipping a flying human."
prompt = "Zombies trying to kill Meg Myers."
prompt = "Meg Myers with an Egyptian dress killing a vampire with a gun."
prompt = "Meg Myers grabbing a vampire by the scruff of the neck."
prompt = "Mark Zuckerberg chokes a vampire to death."
prompt = "Mark Zuckerberg riding an animal."
prompt = "A giant cute animal worshipped by zombies."
prompt = "Several faces."
prompt = "An armoured Yann LeCun fighting tentacles in the jungle."
prompt = "Tentacles everywhere."
prompt = "A photo of a smiling Medusa."
prompt = "Medusa."
prompt = "Meg Myers in bloody armor fending off tentacles with a sword."
prompt = "A red-haired woman with red hair. Her head is tilted."
prompt = "A bloody heavy-metal zombie with a chainsaw."
prompt = "Tentacles attacking a bloody Meg Myers in Eyptian dress. Meg Myers has a chainsaw."
prompt = "Bizarre art."
prompt = "Beautiful bizarre woman."
prompt = "Yann LeCun as the grim reaper: bizarre art."
prompt = "Un chat en sang et en armure joue de la batterie."
prompt = "Photo of a cyberpunk Mark Zuckerberg killing Cthulhu with a light saber."
prompt = "A ferocious cyborg bear."
prompt = "Photo of Mark Zuckerberg killing Cthulhu with a light saber."
prompt = "A bear with horns and blood and big teeth."
prompt = "A photo of a bear and Yoda, good friends."
prompt = "A photo of Yoda on the left, a blue octopus on the right, an explosion in the center."
prompt = "A bird is on a hippo. They fight a black and red octopus. Jungle in the background."
prompt = "A flying white owl above 4 colored pots with fire. The owl has a hat."
prompt = "A flying white owl above 4 colored pots with fire."
prompt = "Yann LeCun rides a dragon which spits fire on a cherry on a cake."
prompt = "An armored Mark Zuckerberg fighting off a monster with bloody tentacles in the jungle with a light saber."
prompt = "Cute woman, portrait, photo, red hair, green eyes, smiling."
prompt = "Photo of Tarzan as a lawyer with a tie and an octopus on his head."
prompt = "An armored bloody Yann Lecun has a lightsabar and fights a red tentacular monster."
prompt = "Photo of a giant armored insect attacking a building. The building is broken. There are flames."
prompt = "Photo of Meg Myers, on the left, in Egyptian dress, fights Cthulhu (on the right) with a light saber. They stare at each other."
prompt = "Photo of a cute red panda."
prompt = "Photo of a cute smiling white-haired woman with pink eyes."
prompt = "A muscular Jesus with and assault rifle, a cap and and a light saber."
prompt = "A portrait of a cute smiling woman."
prompt = "A woman with black skin, red hair, egyptian dress, yellow eyes."
prompt = "Photo of a red haired man with tilted head."
prompt = "A photo of Cleopatra with Egyptian Dress kissing Yoda."
prompt = "A photo of Yoda fighting Meg Myers with light sabers."
prompt = "A photo of Meg Myers, laughing, pulling Gandalf's hair."
prompt = "A photo of Meg Myers laughing and pulling Gandalf's hair. Gandalf is stooping."
prompt = "A star with flashy colors."
prompt = "Portrait of a green haired woman with blue eyes."
prompt = "Portrait of a female kung-fu master."
prompt = "In a dark cave, in the middle of computers, a bearded red-haired geek with squared glasses meets the devil."
prompt = "Photo of the devil, with horns. There are flames in the background."
prompt = "Yann LeCun fighting Pinocchio with light sabers."
prompt = "Yann LeCun attacks a triceratops with a lightsaber."
prompt = "A cyberpunk man next to a cyberpunk woman."
prompt = "A smiling woman with a Katana and electronic patches."
prompt = "Photo of a bearded, long-haired man with glasses and a blonde-haired woman. Both are smiling. Cats and drums and computers on shelves in the background."
prompt = "Photo of a nuclear mushroom in Paris."
prompt = "Three cute monsters."
prompt = "A photo of a ninja holding a cucumber and facing a dinosaur."
prompt = "A ninja fighting a dinosaur with a cucumber."
prompt = "A photo of a cyberpunk cute woman with green hair, a red dress, and a gun. Futuristic backgroundd."
prompt = "A woman with many arms playing music."
prompt = "Conan the Barbarian eating an ice-cream and a cotton candy."
prompt = "Conan the Barbarian hugs a Minion. There is a rainbow."
print(f"The prompt is {prompt}")


# A welcome message.
print(pyfiglet.figlet_format("Welcome in Genetic Stable Diffusion !"))
print(pyfiglet.figlet_format("First, let us choose the text :-)!"))


# Possibly changing the prompt.
print(f"Francais: Proposez un nouveau texte si vous ne voulez pas dessiner << {prompt} >>.\n")
speak("Hey!")
user_prompt = input(f"English: Enter a new prompt if you prefer something else than << {prompt} >>.\n")
if len(user_prompt) > 2:
    prompt = user_prompt

# On the fly translation.
language = detect(prompt)
english_prompt = GoogleTranslator(source='auto', target='en').translate(prompt)
def to_native(stri):
    return GoogleTranslator(source='en', target=language).translate(stri)

# We have all we need for a pretty printing.
def pretty_print(stri):
    print(pyfiglet.figlet_format(to_native(stri)))
print(f"{to_native('Working on')} {english_prompt}, a.k.a {prompt}.")


# Converting a latent var to an image.
def latent_to_image(latent):
    os.environ["forcedlatent"] = str(list(latent.flatten()))  #str(list(forcedlatents[k].flatten()))            
    with autocast("cuda"):
         image = pipe(english_prompt, guidance_scale=gs, num_inference_steps=num_iterations)["sample"][0]
    os.environ["forcedlatent"] = "[]"
    return image

# Creating the super-resolution stuff. RealESRGAN is fantastic!
sr_device = torch.device('cpu') #device #('mps')   #torch.device('cuda' if torch.cuda.is_available() else 'cpu')
esrmodel = RealESRGAN(sr_device, scale=4)
esrmodel.load_weights('weights/RealESRGAN_x4.pth', download=True)
esrmodel2 = RealESRGAN(sr_device, scale=2)
esrmodel2.load_weights('weights/RealESRGAN_x2.pth', download=True)

# Face enhancing.
def fe(path):
    fe = GFPGANer(model_path='GFPGANv1.3.pth', upscale=2, arch='clean', channel_multiplier=2)
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    _, _, output = fe.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
    cv2.imwrite(path, output)

# RealESRGan for convenient super-resolution.
def singleeg(path_to_image):
    image = Image.open(path_to_image).convert('RGB')
    sr_device = device #('mps')   #torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Type before SR = {type(image)}")
    sr_image = esrmodel.predict(image)
    print(f"Type after SR = {type(sr_image)}")
    output_filename = path_to_image + ".SR.png"
    sr_image.save(output_filename)
    fe(output_filename)
    return output_filename

# A version with x2.
def singleeg2(path_to_image):
    image = Image.open(path_to_image).convert('RGB')
    sr_device = device #('mps')   #torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"Type before SR = {type(image)}")
    sr_image = esrmodel2.predict(image)
    print(f"Type after SR = {type(sr_image)}")
    output_filename = path_to_image + ".SR.png"
    sr_image.save(output_filename)
    fe(output_filename)
    return output_filename


# realESRGan applied to many files.
def eg(list_of_files, last_list_of_files):
    pretty_print("Should I convert images below to high resolution ?")
    print(list_of_files)
    print("Last iteration:")
    print(last_list_of_files)
    speak("Go to the text window!")
    answer = input(" [y]es / [n]o / [j]ust the ones in last iteration ?")
    if "y" in answer or "Y" in answer or "j" in answer or "J" in answer:
        if "j" in answer or "J" in answer:
            list_of_files = last_list_of_files
        #images = Parallel(n_jobs=12)(delayed(singleeg)(image) for image in list_of_files)
        #print(to_native(f"Created the super-resolution files {images}")) 
        for path_to_image in list_of_files:
            output_filename = singleeg(path_to_image)
            print(to_native(f"Created the super-resolution file {output_filename}")) 

# When we stop the run and check and propose to do super-resolution and/or animations.
def stop_all(list_of_files, list_of_latent, last_list_of_files, last_list_of_latent):
    print(to_native("Do you want to run 300 variations of your last click ?"))
    res = input("[Y]es or [N]o")
    if "y" in res or "Y" in res:
        pretty_print("Generating 300 variations (you can Ctrl-C if you are bored).")
        pretty_print("You can rerun afterwards, and resume from your favorite one.")
        all_new_latents = multi_combine([list_of_latent[-1]], [(0, .5, .5)], 300)
        for i, l in enumerate(all_new_latents):
            img = latent_to_image(l)
            image_name = f"variation_{i}.png"
            img.save(image_name)
            str_latent = str(list(l))
            with open(image_name + ".latent.txt", 'w') as f:
                f.write(f"{str_latent}")
        exit()
    print(to_native("Your selected images and the last generation:"))
    print(list_of_files)
    eg(list_of_files, last_list_of_files)
    pretty_print("Should we create animations ?")
    answer = input(" [y]es or [n]o or [j]ust the selection on the last panel ?")
    if "y" in answer or "Y" in answer or "j" in answer or "J" in answer:
        assert len(list_of_files) == len(list_of_latent)
        if "j" in answer or "J" in answer:
            list_of_latent = last_list_of_latent
            list_of_files = last_list_of_files
        pretty_print("Let us create animations!")
        for c in sorted([0.0025, 0.005, 0.01, 0.02]):
            for idx in range(len(list_of_files)):
                images = []
                l = list_of_latent[idx].reshape(1,4,64,64)
                l = np.sqrt(len(l.flatten()) / np.sum(l**2)) * l
                l1 = l + c * np.random.randn(len(l.flatten())).reshape(1,4,64,64)
                l1 = np.sqrt(len(l1.flatten()) / np.sum(l1**2)) * l1
                l2 = l + c * np.random.randn(len(l.flatten())).reshape(1,4,64,64)
                l2 = np.sqrt(len(l2.flatten()) / np.sum(l2**2)) * l2
                num_animation_steps = 13
                index = 0
                for u in np.linspace(0., 2*3.14159 * (1-1/30), 30):
                     cc = np.cos(u)
                     ss = np.sin(u*2)
                     index += 1
                     image = latent_to_image(l + cc * (l1 - l) + ss * (l2 - l))
                     image_name = f"imgA{index}.png"
                     image.save(image_name)
                     fe(image_name)
                     images += [image_name]
                     
                print(to_native(f"Base images created for perturbation={c} and file {list_of_files[idx]}"))
                images = Parallel(n_jobs=10)(delayed(singleeg2)(image) for image in images)
                frames = [Image.open(image) for image in images]
                frame_one = frames[0]
                gif_name = list_of_files[idx] + "_" + str(c) + ".gif"
                frame_one.save(gif_name, format="GIF", append_images=frames,
                      save_all=True, duration=100, loop=0)    
    
    pretty_print("Good bye!")
    exit()


      

# Optionally, we start from an image (possibly a drawing, or toys, or whatever).
pretty_print("Now let us choose (if you want) an image as a start.")
image_name = input(to_native("Name of image for starting ? (enter if no start image)"))

# activate the pygame library .
pygame.init()
X = 2000  # > 1500 = buttons
Y = 900  
scrn = pygame.display.set_mode((1700, Y + 100))
font = pygame.font.Font('freesansbold.ttf', 22)
minifont = pygame.font.Font('freesansbold.ttf', 15)
bigfont = pygame.font.Font('freesansbold.ttf', 44)

def load_img(path):
    image = Image.open(path).convert("RGB")
    w, h = image.size
    print(to_native(f"loaded input image of size ({w}, {h}) from {path}"))
    w, h = map(lambda x: x - x % 32, (w, h))  # resize to integer multiple of 32
    image = image.resize((512, 512), resample=PIL.Image.LANCZOS)
    image = np.array(image).astype(np.float32) / 255.0
    image = image[None].transpose(0, 3, 1, 2)
    image = torch.from_numpy(image)
    return 2.*image - 1.


# We need the model for the image to latent conversions.
model = pipe.vae

def img_to_latent(path):
    #init_image = 1.8 * load_img(path).to(device)
    init_image = load_img(path).to(device)
    init_image = repeat(init_image, '1 ... -> b ...', b=1)
    forced_latent = model.encode(init_image.to(device)).latent_dist.sample()
    new_fl = forced_latent.cpu().detach().numpy().flatten()
    new_fl = np.sqrt(len(new_fl)) * new_fl / np.sqrt(np.sum(new_fl ** 2))
    return new_fl

def randomized_image_to_latent(image_name, scale=None, epsilon=None, c=None, f=None):
    base_init_image = load_img(image_name).to(device)
    new_base_init_image = base_init_image
    c = np.exp(np.random.randn()) if c is None else c
    f = np.exp(-3. * np.random.rand()) if f is None else f
    init_image_shape = base_init_image.cpu().numpy().shape
    init_image = c * new_base_init_image
    init_image = repeat(init_image, '1 ... -> b ...', b=1)
    forced_latent = 1. * model.encode(init_image.to(device)).latent_dist.sample()
    new_fl = forced_latent.cpu().detach().numpy().flatten()
    basic_new_fl = new_fl  #np.sqrt(len(new_fl) / sum(new_fl ** 2)) * new_fl
    basic_new_fl = f * np.sqrt(len(new_fl) / np.sum(basic_new_fl**2)) * basic_new_fl
    epsilon = 0.1 * np.exp(-3 * np.random.rand()) if epsilon is None else epsilon
    new_fl = (1. - epsilon) * basic_new_fl + epsilon * np.random.randn(1*4*64*64)
    scale = 2.8 + 3.6 * np.random.rand() if scale is None else scale
    new_fl = scale * np.sqrt(len(new_fl)) * new_fl / np.sqrt(np.sum(new_fl ** 2))
    return new_fl

# In case the user wants to start from a given image.
if len(image_name) > 0:
    pretty_print("Importing an image !")
    try:
        init_image = load_img(image_name).to(device)
    except:
        pretty_print("Try again!")
        pretty_print("Loading failed!!")
        image_name = input(to_native("Name of image for starting ? (enter if no start image)"))
        
    base_init_image = load_img(image_name).to(device)
    speak("Image loaded!")
    print(base_init_image.shape)
    print(np.max(base_init_image.cpu().detach().numpy().flatten()))
    print(np.min(base_init_image.cpu().detach().numpy().flatten()))
    
    forcedlatents = []
    latent_found = False
    try:
        latent_file = image_name + ".latent.txt"
        print(to_native(f"Trying to load latent variables in {latent_file}."))
        f = open(latent_file, "r")
        latent_str = f.read()
        print("Latent string read.")
        latent_found = True
    except:
        print(to_native("No latent file: guessing."))
        for i in range(llambda):
            forcedlatents += [randomized_image_to_latent(image_name)]  #img_to_latent(voronoi_name)
    if latent_found:
        print(to_native("File opened."))
        for i in range(llambda):
            basic_new_fl = np.asarray(eval(latent_str))
            if i > 0:
                f = np.exp(-3. * np.random.rand())
                basic_new_fl = f * np.sqrt(len(new_fl) / np.sum(basic_new_fl**2)) * basic_new_fl
                epsilon = .7 * ((i-1)/(llambda-1)) #1.0 / 2**(2 + (llambda - i) / 6)
                #print(f"{i} -- {i % 7} {c} {f} {epsilon}")
                new_fl = (1. - epsilon) * basic_new_fl + epsilon * np.random.randn(1*4*64*64)
                new_fl = np.sqrt(len(new_fl)) * new_fl / np.sqrt(np.sum(new_fl ** 2))
            else:
                new_fl = basic_new_fl
            forcedlatents += [new_fl]


# We start the big time consuming loop!
for iteration in range(3000):   # Kind of an infinite loop.
    latent = [latent[f] for f in five_best]
    images = [images[f] for f in five_best]
    onlyfiles = [onlyfiles[f] for f in five_best]
    early_stop = []
    speak("Wait!")
    final_selection = []
    final_selection_latent = []
    for k in range(llambda):
        if len(early_stop) > 0:
            break
        max_created_index = k
        if k < len(forcedlatents):
            latent_forcing = str(list(forcedlatents[k].flatten()))
            print(f"We play with {latent_forcing[:20]}")
        if k < len(five_best):
            imp = pygame.transform.scale(pygame.image.load(onlyfiles[k]).convert(), (300, 300))
            scrn.blit(imp, (300 * (k // 3), 300 * (k % 3)))
            pygame.display.flip()
            continue
        pygame.draw.rect(scrn, black, pygame.Rect(0, Y, 1700, Y+100))
        pygame.draw.rect(scrn, black, pygame.Rect(1500, 0, 2000, Y+100))
        text0 = bigfont.render(to_native(f'Please wait !!! {k} / {llambda}'), True, green, blue)
        scrn.blit(text0, ((X*3/4)/2 - X/32, Y/2-Y/4))
        text0 = font.render(to_native(f'Or, for an early stopping,'), True, green, blue)
        scrn.blit(text0, ((X*3/4)/3 - X/32, Y/2-Y/8))
        text0 = font.render(to_native(f'click <here> and WAIT a bit'), True, green, blue)
        scrn.blit(text0, ((X*3/4)/3 - X/32, Y/2))
        text0 = font.render(to_native(f'... ... ... '), True, green, blue)
        scrn.blit(text0, ((X*3/4)/2 - X/32, Y/2+Y/8))

        text1 = minifont.render(to_native('Undo: click <here> for '), True, green, blue)
        text1 = pygame.transform.rotate(text1, 90)
        scrn.blit(text1, (X*3/4+X/16+X/64 - X/32, Y/12))
        text1 = minifont.render(to_native('resetting your clicks.'), True, green, blue)
        text1 = pygame.transform.rotate(text1, 90)
        scrn.blit(text1, (X*3/4+X/16+X/32 - X/32, Y/12))
        # Button for quitting and effects
        text2 = font.render(to_native(f'Total: {len(all_selected)} chosen images! '), True, green, blue)
        text2 = pygame.transform.rotate(text2, 90)
        scrn.blit(text2, (X*3/4+X/16      - X/32, Y/3))
        text2 = font.render(to_native('Click <here> for stopping,'), True, green, blue)
        text2 = pygame.transform.rotate(text2, 90)
        scrn.blit(text2, (X*3/4+X/16+X/64 - X/32, Y/3))
        text2 = font.render(to_native('and get the effects.'), True, green, blue)
        text2 = pygame.transform.rotate(text2, 90)
        scrn.blit(text2, (X*3/4+X/16+X/32 - X/32, Y/3))

        pygame.display.flip()
        os.environ["earlystop"] = "False" if k > len(five_best) else "True"
        os.environ["epsilon"] = str(0. if k == len(five_best) else (k - len(five_best)) / llambda)
        os.environ["budget"] = str(np.random.randint(400) if k > len(five_best) else 2)
        # The line below compares several learning tools but it turns out that decision trees are better seemingly.
        # os.environ["skl"] = {0: "nn", 1: "tree", 2: "logit"}[k % 3]
        os.environ["skl"] = "tree"
        previous_gs = gs
        if k < len(forcedgs):
            gs = forcedgs[k]
        image = latent_to_image(np.asarray(latent_forcing)) #eval(os.environ["forcedlatent"])))
        gs = previous_gs

        images += [image]
        filename = f"SD_{prompt.replace(' ','_')}_image_{sentinel}_{iteration:05d}_{k:05d}.png"  
        image.save(filename)
        fe(filename)
        onlyfiles += [filename]
        imp = pygame.transform.scale(pygame.image.load(onlyfiles[-1]).convert(), (300, 300))
        scrn.blit(imp, (300 * (k // 3), 300 * (k % 3)))
        pygame.display.flip()
        print('\a')  # beep!
        str_latent = eval((os.environ["latent_sd"]))
        array_latent = eval(f"np.array(str_latent).reshape(4, 64, 64)")
        print(f"Debug info: array_latent sumsq/var {sum(array_latent.flatten() ** 2) / len(array_latent.flatten())}")
        latent += [array_latent]
        with open(filename + ".latent.txt", 'w') as f:
            f.write(f"{str_latent}")

        # In case of early stopping, we stop the loop.
        first_event = True
        for i in pygame.event.get():
            if i.type == pygame.MOUSEBUTTONUP:
                if first_event:
                    speak("Ok I stop!")
                    first_event = False
                pos = pygame.mouse.get_pos()
                index = 3 * (pos[0] // 300) + (pos[1] // 300)
                if pos[0] > X and pos[1] > Y /3 and pos[1] < 2*Y/3:
                    stop_all(all_selected, all_selected_latent, final_selection, final_selection_latent)
                    exit()
                if index <= k:
                    pretty_print(("You clicked for requesting an early stopping."))
                    early_stop = [pos]
                    break
                early_stop = [(1,1)]
                satus = False
    forcedgs = []

    speak("Please choose!")
    pretty_print("Please choose your images.")
    text0 = bigfont.render(to_native(f'Choose your favorite images !!!========='), True, green, blue)
    scrn.blit(text0, ((X*3/4)/2 - X/32, Y/2-Y/4))
    text0 = font.render(to_native(f'=================================='), True, green, blue)
    scrn.blit(text0, ((X*3/4)/3 - X/32, Y/2-Y/8))
    text0 = font.render(to_native(f'=================================='), True, green, blue)
    scrn.blit(text0, ((X*3/4)/3 - X/32, Y/2))
    # Add rectangles
    pygame.draw.rect(scrn, red, pygame.Rect(X*3/4, 0, X*3/4+X/16+X/32, Y/3), 2)
    pygame.draw.rect(scrn, red, pygame.Rect(X*3/4, Y/3, X*3/4+X/16+X/32, 2*Y/3), 2)
    pygame.draw.rect(scrn, red, pygame.Rect(X*3/4, 2*Y/3, X*3/4+X/16+X/32, Y), 2)
    pygame.draw.rect(scrn, red, pygame.Rect(0, Y, X/2, Y+100), 2)

    # Button for stopping now.
    text2 = font.render(to_native('Click <here>,'), True, green, blue)
    text2 = pygame.transform.rotate(text2, 90)
    scrn.blit(text2, (X*3/4+X/16 - X/32, Y/3+10))
    text2 = font.render(to_native('for finishing with effects.'), True, green, blue)
    text2 = pygame.transform.rotate(text2, 90)
    scrn.blit(text2, (X*3/4+X/16+X/32 - X/32, Y/3+10))
    text2 = font.render(to_native('or manually edit.'), True, green, blue)
    text2 = pygame.transform.rotate(text2, 90)
    scrn.blit(text2, (X*3/4+X/16+X/32 , Y/3+10))

    # Button for new generation
    text3 = font.render(to_native(f"I don't want to select images"), True, green, blue)
    text3 = pygame.transform.rotate(text3, 90)
    scrn.blit(text3, (X*3/4+X/16 - X/32, Y*2/3+10))
    text3 = font.render(to_native(f"Just rerun."), True, green, blue)
    text3 = pygame.transform.rotate(text3, 90)
    scrn.blit(text3, (X*3/4+X/16+X/32 - X/32, Y*2/3+10))
    text4 = font.render(to_native(f"Modify parameters or text!"), True, green, blue)
    scrn.blit(text4, (300, Y + 30))
    pygame.display.flip()

    for idx in range(max_created_index + 1):
        # set the pygame window name
        pygame.display.set_caption(prompt)
        print(to_native(f"Pasting image {onlyfiles[idx]}..."))
        imp = pygame.transform.scale(pygame.image.load(onlyfiles[idx]).convert(), (300, 300))
        scrn.blit(imp, (300 * (idx // 3), 300 * (idx % 3)))
     
    # paint screen one time
    pygame.display.flip()
    status = True
    indices = []
    good = []
    five_best = []
    for i in pygame.event.get():
        if i.type == pygame.MOUSEBUTTONUP:
            print(to_native(".... too early for clicking !!!!"))


    pretty_print("Please click on your favorite elements!")
    print(to_native("You might just click on one image and we will provide variations."))
    print(to_native("Or you can click on the top of an image and the bottom of another one."))
    print(to_native("Click on the << new generation >> when you're done.")) 
    while (status):
     
      # iterate over the list of Event objects
      # that was returned by pygame.event.get() method.
        for i in pygame.event.get():
            if hasattr(i, "type") and i.type == pygame.MOUSEBUTTONUP:
                pos = pygame.mouse.get_pos() 
                pretty_print(f"Detected! Click at {pos}")
                if pos[1] > Y:
                    pretty_print("Let us update parameters!")
                    text4 = font.render(to_native(f"ok, go to text window!"), True, green, blue)
                    scrn.blit(text4, (300, Y + 30))
                    pygame.display.flip()
                    try:
                        num_iterations = int(input(to_native(f"Number of iterations ? (current = {num_iterations})\n")))
                    except:
                        num_iterations = int(input(to_native(f"Number of iterations ? (current = {num_iterations})\n")))
                    gs = float(input(to_native(f"Guidance scale ? (current = {gs})\n")))
                    print(to_native(f"The current text is << {prompt} >>."))
                    print(to_native("Start your answer with a symbol << + >> if this is an edit and not a new text.")) 
                    new_prompt = str(input(to_native(f"Enter a text if you want to change from ") + prompt))
                    if len(new_prompt) > 2:
                        if new_prompt[0] == "+":
                            prompt += new_prompt[1:]
                        else:
                            prompt = new_prompt
                        language = detect(prompt)
                        english_prompt = GoogleTranslator(source='auto', target='en').translate(prompt)
                    pretty_print("Ok! Parameters updated.")
                    pretty_print("==> go back to the window!")
                    text4 = font.render(to_native(f"Ok! parameters changed!"), True, green, blue)
                    scrn.blit(text4, (300, Y + 30))
                    pygame.display.flip()
                    break
                elif pos[0] > 1500:  # Not in the images.
                    print(to_native("Right hand panel."))
                    if pos[1] < Y/3:  # Reinitialize the clicks!
                        print(to_native("Reinitialize clicks."))
                        indices = []
                        good = []
                        final_selection = []
                        final_selection_latent = []
                        break
                    elif pos[1] < 2*Y/3:
                        print(to_native("stop all"))
                        assert len(onlyfiles) == len(latent)
                        assert len(all_selected) == len(all_selected_latent)
                        stop_all(all_selected, all_selected_latent, final_selection, final_selection_latent) # + onlyfiles, all_selected_latent + latent)
                        exit()
                    status = False
                index = 3 * (pos[0] // 300) + (pos[1] // 300)
                pygame.draw.circle(scrn, red, [pos[0], pos[1]], 13, 0)
                if index <= max_created_index:  # The user has clicked on an image!
                    selected_filename = to_native("Selected") + onlyfiles[index]
                    shutil.copyfile(onlyfiles[index], selected_filename)
                    assert len(onlyfiles) == len(latent), f"{len(onlyfiles)} != {len(latent)}"
                    all_selected += [selected_filename]
                    all_selected_latent += [latent[index]]
                    final_selection += [selected_filename]
                    final_selection_latent += [latent[index]]
                    text2 = font.render(to_native(f'==> {len(all_selected)} chosen images! '), True, green, blue)
                    text2 = pygame.transform.rotate(text2, 90)
                    scrn.blit(text2, (X*3/4+X/16      - X/32, Y/3))
                    if index not in five_best and len(five_best) < 5:
                        five_best += [index]
                        good += [list(latent[index].flatten())]
                    indices += [[index, (pos[0] - (pos[0] // 300) * 300) / 300, (pos[1] - (pos[1] // 300) * 300) / 300]]
                    # Update the button for new generation.
                    pygame.draw.rect(scrn, black, pygame.Rect(X*3/4, 2*Y/3, X*3/4+X/16+X/32, Y))
                    pygame.draw.rect(scrn, red, pygame.Rect(X*3/4, 2*Y/3, X*3/4+X/16+X/32, Y), 2)
                    text3 = font.render(to_native(f"  You have chosen {len(indices)} images:"), True, green, blue)
                    text3 = pygame.transform.rotate(text3, 90)
                    scrn.blit(text3, (X*3/4+X/16 - X/32, Y*2/3))
                    text3 = font.render(to_native(f"  Click <here> for new generation!"), True, green, blue)
                    text3 = pygame.transform.rotate(text3, 90)
                    scrn.blit(text3, (X*3/4+X/16+X/32 - X/32, Y*2/3))
                    pygame.display.flip()
                elif len(indices) == 0:
                    speak("Bad click ! Click on an image.")
                    pretty_print("Bad click! Click on image.")
    
            if i.type == pygame.QUIT:
                status = False
     
    # Covering old images with full circles.
    for _ in range(123):
        x = np.random.randint(1500)
        y = np.random.randint(900)
        pygame.draw.circle(scrn, darkgreen,
                           [x, y], 17, 0)
    pygame.display.update()
    if len(indices) == 0:
        print("The user did not like anything! Rerun :-(")
        continue
    print(f"Clicks at {indices}")
    os.environ["mu"] = str(len(indices))
    forcedlatents = []
    bad += [list(latent[u].flatten()) for u in range(len(onlyfiles)) if u not in [i[0] for i in indices]]

    # No more than 500 bad images.
    if len(bad) > 500:
        bad = bad[(len(bad) - 500):]
    print(to_native(f"{len(indices)} indices are selected."))

    # This is hackish, we communicate with the diffusers code using environment variables... sorry.
    os.environ["good"] = str(good)
    os.environ["bad"] = str(bad)
    numpy_images = [np.array(image) for image in images]
    if len(np.unique([i[0] for i in indices])) == 1:
       sigma = 0.7 * sigma
    forcedlatents += multi_combine(latent, indices, llambda)
    os.environ["good"] = "[]"
    os.environ["bad"] = "[]"
            
pygame.quit()
