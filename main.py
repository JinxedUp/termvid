import cv2
import argparse
import os
import numpy as np
import subprocess
import threading
import time
from colorama import init, Style
import sys
import shutil

init()  # Initialize colorama for colored output

ascii_chars = " .:-=+*#%@"  # Characters for grayscale representation

def clear_terminal():
    print("\033[H\033[J", end="")  # Clear screen + move cursor to top-left

def get_terminal_resolution():
    size = shutil.get_terminal_size(fallback=(80, 24))
    return max(1, size.columns), max(1, size.lines)

def frame_to_ascii_colored(frame, term_width, term_height):
    frame = cv2.resize(frame, (term_width, term_height - 2))
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    output = ""
    for y in range(gray.shape[0]):
        for x in range(gray.shape[1]):
            b, g, r = frame[y, x]
            brightness = gray[y, x]
            c = ascii_chars[int(brightness / 256 * len(ascii_chars))]
            output += f"\033[38;2;{r};{g};{b}m{c}"
        output += Style.RESET_ALL + "\n"
    return output

def frame_to_colored_blocks(frame, term_width, term_height):
    frame = cv2.resize(frame, (term_width, term_height - 2))
    output = ""
    for y in range(frame.shape[0]):
        for x in range(frame.shape[1]):
            b, g, r = frame[y, x]
            output += f"\033[38;2;{r};{g};{b}m█"
        output += Style.RESET_ALL + "\n"
    return output

def extract_audio(input_path, output_audio="temp_audio.aac"):
    subprocess.run([
        "ffmpeg", "-y", "-i", input_path,
        "-vn", "-acodec", "aac", "-filter:a", "volume=0.5",
        output_audio
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_audio

def play_audio(path):
    subprocess.call([
        "ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet",
        "-volume", "100", path
    ])

def play_video(path, use_ascii=True):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30
    frame_time = 1 / fps
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    term_width, term_height = get_terminal_resolution()
    audio_path = extract_audio(path)
    start_time = time.perf_counter()

    audio_thread = threading.Thread(target=play_audio, args=(audio_path,), daemon=True)
    audio_thread.start()

    for i in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break

        target_time = i * frame_time
        now = time.perf_counter() - start_time
        delay = target_time - now
        if delay > 0:
            time.sleep(delay)

        clear_terminal()
        print(
            frame_to_ascii_colored(frame, term_width, term_height)
            if use_ascii else
            frame_to_colored_blocks(frame, term_width, term_height)
        )

    cap.release()
    os.remove(audio_path)
    return use_ascii

def save_as_video(original_path, use_ascii):
    print("\n💾 Would you like to save this terminal render as a video? (y/n): ", end="")
    choice = input().strip().lower()
    if choice != "y":
        return

    output_name = f"terminal+{os.path.basename(original_path)}"
    output_path = os.path.join(os.path.dirname(original_path), output_name)

    term_width, term_height = get_terminal_resolution()
    cap = cv2.VideoCapture(original_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps):
        fps = 30
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    frames = []
    for _ in range(frame_count):
        ret, frame = cap.read()
        if not ret:
            break
        frame = cv2.resize(frame, (term_width, term_height - 2))
        if use_ascii:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            canvas = np.zeros_like(frame)
            for y in range(gray.shape[0]):
                for x in range(gray.shape[1]):
                    brightness = gray[y, x]
                    char = ascii_chars[int(brightness / 256 * len(ascii_chars))]
                    b, g, r = frame[y, x]
                    canvas[y, x] = (b, g, r)
            frame = canvas
        frames.append(frame)
    cap.release()

    temp_frames_dir = "tempframes"
    os.makedirs(temp_frames_dir, exist_ok=True)
    for i, f in enumerate(frames):
        cv2.imwrite(f"{temp_frames_dir}/frame{i:04}.png", f)

    temp_audio = extract_audio(original_path, "temp_audio_output.aac")

    subprocess.run([
        "ffmpeg", "-y",
        "-r", str(fps),
        "-i", f"{temp_frames_dir}/frame%04d.png",
        "-i", temp_audio,
        "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-movflags", "+faststart",
        "-shortest",
        output_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    shutil.rmtree(temp_frames_dir)
    os.remove(temp_audio)
    print(f"\n✅ Saved as {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="🎥 Play a video in your terminal with color and synced audio!")
    parser.add_argument("file", help="Path to video file (.mp4/.mkv)")
    parser.add_argument("--ascii", action="store_true", help="Render using ASCII mode")

    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print("❌ File not found:", args.file)
        sys.exit(1)

    ascii_mode_used = play_video(args.file, use_ascii=args.ascii)
    save_as_video(args.file, ascii_mode_used)
