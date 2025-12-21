This app takes a racetime.gg link and automatically adds the player streams to an obs layout specifically made for hitman SN Races

[Linux install video](https://youtu.be/cg9OBavoEqw)

Windows video coming eventually when linux is confirmed to be working

Usage Instructions/Notes:
-Import the scene to obs with Scene Collection -> Import -> Browse -> SN_Race.json in the SNAUTOOBS folder, use the same folder when it asks you to locate the missing images.
-For the OBS password go to Tools -> WebSocket Server Settings -> Show Connect Info -> Server Password.
-Paste in racetime link in full (including https).
-Auto Fill Slots will scan the racetime lobby every 5 seconds and add new players that joined, turning it off will make it stop scanning/adding players.
-Show Placement Images when ticked will automatically show the placement image related to them when they finish.
-Use the arrow buttons to move the players up/down the list and use the trash can button to remove them from the list, you can add them back using the + button in the Removed Players section.
-Ensure that your mic and any other applicable audio sources are configured properly.
-Double click in the .ttf font and click install, restart your pc/obs for the font to apply.
-All placement images have a luma key filter called Toggle_Hook with Luma Max + Min at 1.0 and the smooth for both at 0, this is for the auto placement images toggle functionality.
-You can freely move and resize things like "Steamer Name X" and the stream itself and the program will still work as intended, to move the names click on the source in the appropriate folder, to move/resize the stream just click on it in the preview.
-If you want to move the name to be on top of the video player, remember to drag it above the stream source in the folder.

Future features i have thought of:
-Spotlight one player for the Stream (Zoom) Scene.
-Automate the Leaderboard

if you have any ideas for features open a pr or dm me on discord @Rekt05