import os
import random
import string
import hashlib
from flask import Flask, request, send_file
from PIL import Image
import wave
import zipfile

app = Flask(__name__)

# Set up a folder to save files
UPLOAD_FOLDER = './uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Helper Functions Class
class SteganographyHelper:
    @staticmethod
    def generate_key(length=16):
        """Generate a random key"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

    @staticmethod
    def generate_key_from_file(file_path):
        """Generate a key based on the file name (hashed version)"""
        file_name = os.path.basename(file_path)
        return hashlib.sha256(file_name.encode()).hexdigest()[:16]

    @staticmethod
    def is_image(file_path):
        """Check if the file is an image"""
        return file_path.lower().endswith(('.png', '.jpg', '.jpeg'))

    @staticmethod
    def is_audio(file_path):
        """Check if the file is an audio file"""
        return file_path.lower().endswith(('.wav', '.mp3'))

# Encoding Class for Image and Audio
class SteganographyEncoder:
    def __init__(self, secret_message, key):
        self.secret_message = secret_message
        self.key = key

    def image_steganography_encode(self, image_path, output_path):
        """Encode secret message in an image"""
        image = Image.open(image_path)
        binary_secret = ''.join(format(ord(char), '08b') for char in self.secret_message) + '00000000'

        # Embed the key at the start of the binary secret
        binary_key = ''.join(format(ord(char), '08b') for char in self.key)
        binary_secret = binary_key + binary_secret  # Add key at the beginning

        pixels = list(image.getdata())
        encoded_pixels = []

        for i, pixel in enumerate(pixels):
            if i < len(binary_secret):
                pixel = (pixel[0] & ~1 | int(binary_secret[i]),) + pixel[1:]
            encoded_pixels.append(pixel)

        encoded_image = Image.new(image.mode, image.size)
        encoded_image.putdata(encoded_pixels)
        encoded_image.save(output_path)

    def audio_steganography_encode(self, audio_path, output_path):
        """Encode secret message in an audio file"""
        with wave.open(audio_path, 'rb') as audio:
            frames = bytearray(audio.readframes(audio.getnframes()))
            binary_secret = ''.join(format(ord(char), '08b') for char in self.secret_message) + '00000000'

            # Embed the key at the start of the binary secret
            binary_key = ''.join(format(ord(char), '08b') for char in self.key)
            binary_secret = binary_key + binary_secret  # Add key at the beginning

            for i in range(len(binary_secret)):
                frames[i] = (frames[i] & ~1) | int(binary_secret[i])

            with wave.open(output_path, 'wb') as encoded_audio:
                encoded_audio.setparams(audio.getparams())
                encoded_audio.writeframes(frames)

# Decoding Class for Image and Audio
class SteganographyDecoder:
    def __init__(self, key):
        self.key = key

    def image_steganography_decode(self, image_path):
        """Decode secret message from an image"""
        image = Image.open(image_path)
        binary_key = ''.join(format(ord(char), '08b') for char in self.key)
        binary_secret = ''.join(str(pixel[0] & 1) for pixel in image.getdata())

        # Extract the binary message excluding the key part
        secret_message_bin = binary_secret[len(binary_key):]
        secret_message = ''.join(chr(int(secret_message_bin[i:i+8], 2)) for i in range(0, len(secret_message_bin), 8))
        return secret_message.split('\x00', 1)[0]

    def audio_steganography_decode(self, audio_path):
        """Decode secret message from an audio file"""
        with wave.open(audio_path, 'rb') as audio:
            frames = bytearray(audio.readframes(audio.getnframes()))
            binary_key = ''.join(format(ord(char), '08b') for char in self.key)
            binary_secret = ''.join(str(frames[i] & 1) for i in range(len(frames)))

            # Extract the binary message excluding the key part
            secret_message_bin = binary_secret[len(binary_key):]
            secret_message = ''.join(chr(int(secret_message_bin[i:i+8], 2)) for i in range(0, len(secret_message_bin), 8))
            return secret_message.split('\x00', 1)[0]

# Flask route to handle encoding
@app.route('/encode', methods=['POST'])
def encode():
    file = request.files['file']
    text_file = request.files['text_file']
    
    # Save uploaded files
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    text_file_path = os.path.join(UPLOAD_FOLDER, text_file.filename)
    file.save(file_path)
    text_file.save(text_file_path)
    
    # Read the secret message from the text file
    with open(text_file_path, 'r') as f:
        secret_message = f.read()

    # Generate a random key for encoding
    key = SteganographyHelper.generate_key()

    output_path = os.path.join(UPLOAD_FOLDER, 'encoded_file')

    encoder = SteganographyEncoder(secret_message, key)

    if SteganographyHelper.is_image(file_path):
        output_path += '.png'
        encoder.image_steganography_encode(file_path, output_path)
    elif SteganographyHelper.is_audio(file_path):
        output_path += '.wav'
        encoder.audio_steganography_encode(file_path, output_path)
    else:
        return "Unsupported file type. Please upload an image or audio file.", 400

    # Save the key to a separate file
    key_file_path = os.path.join(UPLOAD_FOLDER, 'key.txt')
    with open(key_file_path, 'w') as key_file:
        key_file.write(key)

    # Create a ZIP file containing the encoded file and key
    zip_filename = 'encoded_files.zip'
    zip_file_path = os.path.join(UPLOAD_FOLDER, zip_filename)

    with zipfile.ZipFile(zip_file_path, 'w') as zipf:
        zipf.write(output_path, os.path.basename(output_path))
        zipf.write(key_file_path, 'key.txt')

    # Return the link to download the ZIP file
    return f"Download your encoded files: <a href='/uploads/{zip_filename}'>Download ZIP</a>"

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(UPLOAD_FOLDER, filename), as_attachment=True)

# Flask route to handle decoding
@app.route('/decode', methods=['POST'])
def decode():
    file = request.files['file']  # The uploaded encoded file
    key_file = request.files['key_file']  # The uploaded key file
    
    # Save uploaded files
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    key_file_path = os.path.join(UPLOAD_FOLDER, key_file.filename)
    file.save(file_path)
    key_file.save(key_file_path)

    # Read the key from the key file
    with open(key_file_path, 'r') as f:
        key = f.read()

    decoder = SteganographyDecoder(key)

    if SteganographyHelper.is_image(file_path):
        secret_message = decoder.image_steganography_decode(file_path)
    elif SteganographyHelper.is_audio(file_path):
        secret_message = decoder.audio_steganography_decode(file_path)
    else:
        return "Unsupported file type", 400

    # Save the decoded message to a text file
    text_file_path = os.path.join(UPLOAD_FOLDER, 'decoded_credentials.txt')
    with open(text_file_path, 'w') as text_file:
        text_file.write(secret_message)

    return send_file(text_file_path, as_attachment=True, download_name='decoded_credentials.txt')

if __name__ == '__main__':
    app.run(debug=True)
