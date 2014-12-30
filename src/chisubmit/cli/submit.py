
#  Copyright (c) 2013-2014, The University of Chicago
#  All rights reserved.
#
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions are met:
#
#  - Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
#
#  - Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
#  - Neither the name of The University of Chicago nor the names of its
#    contributors may be used to endorse or promote products derived from this
#    software without specific prior written permission.
#
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
#  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
#  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
#  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
#  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
#  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
#  POSSIBILITY OF SUCH DAMAGE.

import click

from chisubmit.common.utils import set_datetime_timezone_utc, convert_timezone_to_local
from chisubmit.common import CHISUBMIT_SUCCESS, CHISUBMIT_FAIL
from chisubmit.cli.common import pass_course, save_changes
from chisubmit.repos.factory import RemoteRepositoryConnectionFactory


@click.command(name="submit")
@click.argument('team_id', type=str)    
@click.argument('assignment_id', type=str)
@click.argument('commit', type=str)
@click.argument('extensions', type=int, default=0)
@click.option('--force', is_flag=True)
@click.option('--yes', is_flag=True)
@click.option('--ignore_extensions', is_flag=True)
@pass_course
@save_changes
@click.pass_context  
def submit(ctx, course, team_id, assignment_id, commit, extensions, force, yes, ignore_extensions):
    assignment = course.get_assignment(assignment_id)
    if assignment is None:
        print "Assignment %s does not exist" % assignment_id
        return CHISUBMIT_FAIL
    
    team = course.get_team(team_id)
    if team is None:
        print "Team %s does not exist" % team_id
        return CHISUBMIT_FAIL
    
    extensions_requested = extensions
    
    conn = RemoteRepositoryConnectionFactory.create_connection(course.git_server_connection_string)
    server_type = conn.get_server_type_name()
    git_credentials = ctx.obj['config']['git-credentials']

    if git_credentials is None:
        print "You do not have %s credentials." % server_type
        return CHISUBMIT_FAIL    
    
    conn.connect(git_credentials)        
    commit = conn.get_commit(course, team, commit)
    
    if commit is None:
        print "Commit %s does not exist in repository" % commit
        return CHISUBMIT_FAIL
        
    commit_time_utc = set_datetime_timezone_utc(commit.commit.author.date)
    commit_time_local = convert_timezone_to_local(commit_time_utc)
    
    deadline_utc = assignment.get_deadline()
    deadline_local = convert_timezone_to_local(deadline_utc)
        
    extensions_needed = assignment.extensions_needed(commit_time_utc)
    
    extensions_bad = False
    if extensions_requested < extensions_needed:
        print
        print "The number of extensions you have requested is insufficient."
        print
        print "     Deadline (UTC): %s" % deadline_utc.isoformat()
        print "       Commit (UTC): %s" % commit_time_utc.isoformat()
        print 
        print "   Deadline (Local): %s" % deadline_local.isoformat()
        print "     Commit (Local): %s" % commit_time_local.isoformat()
        print 
        print "You need to request %s extensions." % extensions_needed
        extensions_bad = True
    elif extensions_requested > extensions_needed:
        print        
        print "The number of extensions you have requested is excessive."
        print
        print "     Deadline (UTC): %s" % deadline_utc.isoformat()
        print "       Commit (UTC): %s" % commit_time_utc.isoformat()
        print 
        print "   Deadline (Local): %s" % deadline_local.isoformat()
        print "     Commit (Local): %s" % commit_time_local.isoformat()
        print 
        print "You only need to request %s extensions." % extensions_needed
        extensions_bad = True

    if not ignore_extensions and extensions_bad:
        print
        print "You can use the --ignore-extensions option to submit regardless, but"
        print "you should get permission from the instructor before you do so."
        print
        return CHISUBMIT_FAIL
    elif ignore_extensions and extensions_bad:
        print
        print "WARNING: You are forcing a submission with an incorrect number"
        print "of extensions. Make sure you have approval from the instructor"
        print "to do this."
        
    tag_name = assignment.id
    submission_tag = conn.get_submission_tag(course, team, tag_name)
    
    if submission_tag is not None and not force:
        submission_commit = conn.get_commit(course, team, submission_tag.object.sha)
        print        
        print "Submission tag '%s' already exists" % tag_name
        print "It points to commit %s (%s)" % (submission_commit.commit.sha, submission_commit.commit.message)
        print "If you want to override this submission, please use the --force option"
        return CHISUBMIT_FAIL
    elif submission_tag is not None and force:
        submission_commit = conn.get_commit(course, team, submission_tag.object.sha)
        print
        print "WARNING: Submission tag '%s' already exists" % tag_name
        print "It currently points to commit %s...: %s" % (submission_commit.commit.sha[:8], submission_commit.commit.message)
        print "Make sure you want to overwrite the previous submission tag."
        
    print
    print "You are going to tag your code for %s as ready to grade." % assignment.name
    print "The commit you are submitting is the following:"
    print
    print "      Commit: %s" % commit.commit.sha
    print "        Date: %s" % commit.commit.author.date.isoformat()
    print "     Message: %s" % commit.commit.message
    print "      Author: %s <%s>" % (commit.commit.author.name, commit.commit.author.email)
    if not extensions_bad:
        print
        print "The number of extensions you are requesting (%i) is acceptable." % extensions
        print "Please note that this program does not check how many extensions"
        print "you have left. It only checks whether the number of extensions is"
        print "correct given the deadline for the assignment."
    
    print
    print "Are you sure you want to continue? (y/n): ", 
    
    if not yes:
        yesno = raw_input()
    else:
        yesno = 'y'
        print 'y'
    
    if yesno in ('y', 'Y', 'yes', 'Yes', 'YES'):
        message = "Extensions requested: %i\n" % extensions
        message += "Extensions needed: %i\n" % extensions_needed
        if extensions_bad:
            message += "Extensions bad: yes\n"
            
        if submission_tag is None:
            conn.create_submission_tag(course, team, tag_name, message, commit.commit.sha)
        else:
            conn.update_submission_tag(course, team, tag_name, message, commit.commit.sha)
            
        print
        print "Your submission has been completed."
        #print "You can use 'chisubmit team-assignment-submission-verify' to double-check"
        #print "that your code was correctly tagged as ready to grade."
        
    return CHISUBMIT_SUCCESS

        
