# Background operation

Closing the Kingdom desktop window hides it. The local server, its jobs and
existing connections continue running while the computer remains awake and the
application remains open in the notification area. Double-click the Kingdom
icon or choose **Open Kingdom** to return. Starting Kingdom again opens the
existing instance rather than starting a competing server.

Choose **Quit Kingdom and stop this computer’s server** from the icon’s menu to
stop the backend owned by this desktop instance and exit. Other computers and
independently managed servers are not stopped. If the operating system cannot
create a notification icon, closing the window retains the previous quit
behavior so it cannot leave an inaccessible hidden application.

This does not enable automatic login startup, defeat sleep/shutdown, repair a
lost network connection or supervise external SSH relays. Those require their
own connection/service lifecycle. Headless installations should continue using
their operating system service or container restart policy.
