# Hitman Racetime Automation

This app takes a racetime.gg link and automatically adds the player streams to an OBS layout made for Hitman SN races

It is a combination of the previous standalone SNSASO and SNR variants of the app

The OBS scene collections are based on the original from [ThatObserver](https://www.youtube.com/channel/UCY6kHCCKxcVRcMVf9PBtz6w)

## Installation Guide:
- Go to the [releases](https://github.com/Rekt05/hitman-racetime-automation/releases) and download the latest version for your os
- Extract the zip wherever
- The folder contains the app, Hitman_Racetime_Automation.exe on Windows or Hitman_Racetime_Automation on Linux, and an SNSASO folder and an SNR folder
- Go to OBS (the minimum version needed should be 28)
- Import the scene that matches the mode you want:
    - SNSASO: Scene Collection -> Import -> Browse -> SNSASO.json in the SNSASO folder. When it asks for the missing files, use that same SNSASO folder
    - SNR: Scene Collection -> Import -> Browse -> SNR.json in the SNR folder. When it asks for the missing files, use that same SNR folder
- Select the scene collection you just imported from the dropdown
- Enable the OBS WebSocket server under Tools -> WebSocket Server Settings
- Ensure that your port number is the default (4455)
- Copy your OBS WebSocket Server Password under Tools -> WebSocket Server Settings -> Show Connect Info -> Server Password
- Open the app, pick SNR or SNSASO, and paste the copied password in the box on top
### Misc
- If you want to use the intended font, open the scene folder you imported and double click the .ttf font and click install, then restart your pc/obs for the font to apply
- Ensure that your mic and any other applicable audio sources are configured properly by going to said sources and checking that your devices are selected there
- Discord audio is not included by default as the windows version crashes on linux, to add discord audio for a co caster, add an application audio capture on one scene and paste it as a reference on the others [(see detailed)](#obs-application-audio-capture-setup)

## Usage Guide
- Select SNSASO or SNR at the top before you click start
- Start the app by clicking the "Start" button after you have entered your OBS password
- Click the "Find Current Race" button to automatically find the currently open/active hitman race or paste in the link to a racetime room yourself
- Buttons on both SNR and SNSASO:
    - Name Height: Sets the height of player names (0-100), somewhere between 50 and 90 looks the best
    - Name Position: Sets the player name position in relation to the stream
    - Finished Timer: How long "Auto Removed Finished" before removing finished players (0-45s)
    - Auto Remove Finished: Starts a timer with the above mentioned duration when a player clicks done or dnf on racetime, the other players on the screen stay where they are and the last player from a later scene replaces them
    - Auto Resize Streams: Resizes the streams and positions based on how many players are still on it
    - Reset All Positions: Resets the positions and sizes of streams and names to the original
    - Refresh All Streams: Reloads every stream
    - (6P)/4P/2P/1P: Resizes that screen for that many players, unneeded when "Auto Resize Streams" is active
    - Up/Down: Moves that player up or down a slot
    - Remove: Removes the player and adds them to Removed Players, the substitution of the next player works the same way as the "Auto Remove Finished" logic
    - Refresh: Reloads said stream
    - Audio/No Audio: Chooses the slot that audio is played from, regardless of player movement
    - Multiple Audio: Dictates whether or not a scene can have more than one stream's audio active
    - Swap Players: Swaps the 2 selected slots
- SNR only:
    - Aspect Ratio: Click 16:9 or 16:10 to choose said aspect ratio
    - 6 Players is the default
    - Audio starts on slots 1, 7, and 13
    - Place the spin images in the "Spins" Folder so that they are present on all 3 stream scenes
- SNSASO only:
    - 4 players is the default
    - Audio starts on slots 1, 5, and 9
- Removed players show up under Removed Players, click the + to add a player back
- The name source should sit above the stream in the sources list, otherwise the name will not show on top of the video, but this should never be a problem
- The very bottom bar displays updates when actions occur if you needed to see that for some reason
- If you encounter any unexpected errors mid race just restart the app and it will fix it most of the time

## Update Guide
- Follow the [installation guide](#installation-guide)
- You can copy the config.ini from your old install over so that you dont have to configure things like your obs password or app settings again
- If specified to do so in the release, delete and import the scene collection again

### OBS Application Audio capture setup
- You will have to create an application audio capture or the linux equivalent of a application audio capture for discord in any scene -> name it whatever you want (i used "Discord Audio")
- For "Window" select the one that says discord.exe
- For "Window Match Priority" select "Match title, otherwise find window of same executable"
- Copy the new source (ctrl c/right click copy)
- Paste the new source in all other scenes as a reference (ctrl v/right click paste (reference) - the only option should be reference and duplicate should be greyed out)
you can confirm this worked if it now falls under the audio mixer for each scene and if you change the volume on one scene it also changes on the other

For any issues or suggestions, open a pr or dm me on discord @Rekt05