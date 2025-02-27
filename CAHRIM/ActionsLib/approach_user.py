# -*- coding: utf-8 -*-
'''
Copyright October 2019 Tuyen Nguyen

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

***

Author:      Tuyen Nguyen
Email:       ngtvtuyen@jaist.ac.jp
Affiliation: Robotics Laboratory, Japan Advanced Institute of Science and Technology, Japan
Project:     CARESSES (http://caressesrobot.org/en/)
'''

import time
import math
import sys
sys.path.append("..")
import caressestools.caressestools as caressestools
from CahrimThreads.sensory_hub import DetectUserDepth, Person
from action import Action

console_outputs = {
    0 : ["Looking for the user...", 0],
    1 : ["User found at: x %f, y %f, z %f. Approaching user...", 0]
}

## Action "Approach User".
#
#  Pepper moves towards the user.
#  This action gets information about user's position (x,y,z) from thread DetectUserDepth
#  To run the action without running cahrim.py:
#  - comment the import of caressestools
#  - replace the default value of the "ip" script argument with a string
#  - run the action from the CAHRIM directory through the command:
#  python -m ActionsLib.approach_user_Depth --ip <PEPPER-IP>
class ApproachUser(Action):

    ## The constructor.
    # @param self The object pointer.
    # @param apar ---
    # @param cpar (string) Distance in meters.
    # @param session (qi session) NAOqi session.
    def __init__(self, apar, cpar, session):
        Action.__init__(self, apar, cpar, session)

        # Parse the action parameters
        self.apar = self.apar.split(' ')

        # Parse the cultural parameters
        self.cpar = self.cpar.split(' ')

        self.distance = float(self.cpar[0])

        # Initialize NAOqi services    
        self.motion_service = session.service("ALMotion")
        self.life_service = session.service("ALAutonomousLife")
        self.sPeoplePerception = session.service("ALPeoplePerception")
        self.sBasicAwareness = session.service("ALBasicAwareness")

        self.using_face_reco = DetectUserDepth.isUsingFaceRecognition()

        self.timeout = 5
        self.stop_action_timeout = 4
        self.restored_timeout = DetectUserDepth.timeout

        self.sBasicAwareness.setTrackingMode("Head")

        self.sPeoplePerception.setFastModeEnabled(True)
        self.sPeoplePerception.setMaximumDetectionRange(5)
        self.sPeoplePerception.setTimeBeforePersonDisappears(self.timeout)
        self.sPeoplePerception.setTimeBeforeVisiblePersonDisappears(self.timeout)
        DetectUserDepth.timeout = self.timeout

        self.motion_service.setOrthogonalSecurityDistance(0.10)
        self.motion_service.setTangentialSecurityDistance(0.10)
        
        self.try_again = 0
        self.repeatedTimes = 5
        self.lookingUser = False
        self.user_not_found_timeout = 60

    ## Method executed when the thread is started.
    def run(self):

        timer_start = time.time()
        action_start_time = time.time()

        while not self.is_stopped:

            if time.time() - action_start_time > self.user_not_found_timeout:
                self.is_stopped = True
                self.logger.info("User not found within %d seconds." % self.user_not_found_timeout)
                break

            ## If using face recognition, compute the distance from the detected head, only
            ## if the face of the user is recognized
            if self.using_face_reco:
                if Person.isUserPresent():
                    depth, y, z = DetectUserDepth.getUserPosition()
                else:
                    depth, y, z = None, None, None
            else:
                depth, y, z = DetectUserDepth.getUserPosition()

            if (depth):
                action_start_time = time.time()

                if (self.lookingUser == True):
                    self.stopMove()
                self.lookingUser = False
                self.try_again = 0

                if (depth <= self.distance):

                    if abs(y) > 0.1:
                        self.approach(0, y)
                    else:
                        self.stopMove()
                        ## Wait a few seconds to be sure that the user is still there before stopping the action
                        if time.time() - timer_start > self.stop_action_timeout:
                            self.end()
                            self.is_stopped = True
                else:
                    if console_outputs[1][1] == 0:
                        self.logger.info(console_outputs[1][0] % (depth, y, z))
                        console_outputs[0][1] = 0
                        console_outputs[1][1] = 1

                    self.approach(depth, y)

                    timer_start = time.time()

            else:
                if (self.try_again < self.repeatedTimes):
                    self.try_again = self.try_again + 1
                    time.sleep(0.5)
                else:
                    if console_outputs[0][1] == 0:
                        self.logger.info(console_outputs[0][0])
                        console_outputs[0][1] = 1
                        console_outputs[1][1] = 0
                    self.rotate(0.2)
                    self.lookingUser = True

        self.end()

    ## Rotate Pepper by an angle defined by the parameter "radian".
    #  @param self The object pointer.
    #  @param radian (float) Angle of rotation in radians.
    def rotate(self, radian):
        self.motion_service.move(0,0,radian)

    ## Move Pepper towards the user according to their distance as given by the input parameters.
    #  @param self The object pointer.
    #  @param x (float) Distance of the user along Pepper x axis.
    #  @param y (float) Distance of the user along Pepper y axis.
    def approach(self, x, y):
        if (abs(y) < 0.1):
            y = 0

        ky = 0.4

        if x == 0:
            vel_x = 0
        elif x <= self.distance + 0.2:
            vel_x = 0.05
        else:
            vel_x = 0.2

        vel_y = 0.0
        vel_th = ky * y

        state = self.motion_service.move(vel_x, vel_y, vel_th)

        return state

    ## Move Pepper forward at the speed given by the input parameter.
    #  @param speed (float) Forward speed in meters per second.
    def forward(self, speed):
        self.motion_service.move(speed,0.0,0.0)

    ## Stop any Pepper motion.
    def stopMove(self):
        self.motion_service.stopMove()

    ## Method containing all the instructions that should be executing before terminating the action.
    def end(self):
        self.stopMove()

        self.sPeoplePerception.setFastModeEnabled(False)
        self.sPeoplePerception.setMaximumDetectionRange(1.2 * self.distance)
        self.sPeoplePerception.setTimeBeforePersonDisappears(self.restored_timeout)
        self.sPeoplePerception.setTimeBeforeVisiblePersonDisappears(self.restored_timeout)

        self.motion_service.setOrthogonalSecurityDistance(0.4)
        self.motion_service.setTangentialSecurityDistance(0.1)

        DetectUserDepth.timeout = self.restored_timeout

        if not self.is_stopped:
            self.logger.info("User approached")


if __name__ == "__main__":

    import argparse
    import qi
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--ip", type=str, default=caressestools.Settings.robotIP,
                        help="Robot IP address. On robot or Local Naoqi: use '127.0.0.1'.")
    parser.add_argument("--port", type=int, default=9559,
                        help="Naoqi port number")

    args = parser.parse_args()

    try:
        # Initialize qi framework.
        session = qi.Session()
        session.connect("tcp://" + args.ip + ":" + str(args.port))
        print("\nConnected to Naoqi at ip \"" + args.ip + "\" on port " + str(args.port) + ".\n")

    except RuntimeError:
        print ("Can't connect to Naoqi at ip \"" + args.ip + "\" on port " + str(args.port) + ".\n"
                                                                                              "Please check your script arguments. Run with -h option for help.")
        sys.exit(1)

    caressestools.Settings.robotIP = args.ip

    # Run Action
    apar = ""
    cpar = "1"

    caressestools.startPepper(session, caressestools.Settings.interactionNode)
    
    t = DetectUserDepth(session,None,False)
    t.start()
    
    action = ApproachUser(apar, cpar, session)
    action.run()

    t.stop()
